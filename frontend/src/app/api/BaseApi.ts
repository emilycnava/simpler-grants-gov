import "server-only";

import { compact, isEmpty } from "lodash";
import { environment } from "src/constants/environments";
import {
  ApiRequestError,
  BadRequestError,
  ForbiddenError,
  InternalServerError,
  NetworkError,
  NotFoundError,
  RequestTimeoutError,
  ServiceUnavailableError,
  UnauthorizedError,
  ValidationError,
} from "src/errors";
import { QueryParamData } from "src/services/search/searchfetcher/SearchFetcher";
// TODO (#1682): replace search specific references (since this is a generic API file that any
// future page or different namespace could use)
import { APIResponse } from "src/types/apiResponseTypes";

export type ApiMethod = "DELETE" | "GET" | "PATCH" | "POST" | "PUT";
export interface JSONRequestBody {
  [key: string]: unknown;
}

interface APIResponseError {
  field: string;
  message: string;
  type: string;
}

export interface HeadersDict {
  [header: string]: string;
}

export default abstract class BaseApi {
  // Root path of API resource without leading slash.
  abstract get basePath(): string;

  // API version
  get version() {
    return "v0.1";
  }

  // Namespace representing the API resource
  abstract get namespace(): string;

  // Configuration of headers to send with all requests
  // Can include feature flags in child classes
  get headers(): HeadersDict {
    const headers: HeadersDict = {};

    if (environment.API_AUTH_TOKEN) {
      headers["X-AUTH"] = environment.API_AUTH_TOKEN;
    }
    return headers;
  }

  /**
   * Send an API request.
   */
  async request(
    method: ApiMethod,
    basePath: string,
    namespace: string,
    subPath: string,
    queryParamData?: QueryParamData,
    body?: JSONRequestBody,
    options: {
      additionalHeaders?: HeadersDict;
    } = {},
  ) {
    const { additionalHeaders = {} } = options;
    const url = createRequestUrl(
      method,
      basePath,
      this.version,
      namespace,
      subPath,
      body,
    );
    const headers: HeadersDict = {
      ...additionalHeaders,
      ...this.headers,
    };

    headers["Content-Type"] = "application/json";
    const response = await this.sendRequest(
      url,
      {
        body: method === "GET" || !body ? null : createRequestBody(body),
        headers,
        method,
      },
      queryParamData,
    );

    return response;
  }

  /**
   * Send a request and handle the response
   */
  private async sendRequest(
    url: string,
    fetchOptions: RequestInit,
    queryParamData?: QueryParamData,
  ) {
    let response: Response;
    let responseBody: APIResponse;
    try {
      response = await fetch(url, fetchOptions);
      responseBody = (await response.json()) as APIResponse;
    } catch (error) {
      // API most likely down, but also possibly an error setting up or sending a request
      // or parsing the response.
      throw fetchErrorToNetworkError(error, queryParamData);
    }
    if (!response.ok) {
      handleNotOkResponse(responseBody, url, queryParamData);
    }

    const { data, message, pagination_info, status_code, warnings } =
      responseBody;

    return {
      data,
      message,
      pagination_info,
      status_code,
      warnings,
    };
  }
}

export function createRequestUrl(
  method: ApiMethod,
  basePath: string,
  version: string,
  namespace: string,
  subPath: string,
  body?: JSONRequestBody,
) {
  // Remove leading slash
  const cleanedPaths = compact([basePath, version, namespace, subPath]).map(
    removeLeadingSlash,
  );
  let url = [...cleanedPaths].join("/");
  if (method === "GET" && body && !(body instanceof FormData)) {
    // Append query string to URL
    const body: { [key: string]: string } = {};
    Object.entries(body).forEach(([key, value]) => {
      const stringValue =
        typeof value === "string" ? value : JSON.stringify(value);
      body[key] = stringValue;
    });

    const params = new URLSearchParams(body).toString();
    url = `${url}?${params}`;
  }
  return url;
}

/**
 * Remove leading slash
 */
function removeLeadingSlash(path: string) {
  return path.replace(/^\//, "");
}

/**
 * Transform the request body into a format that fetch expects
 */
function createRequestBody(payload?: JSONRequestBody): XMLHttpRequestBodyInit {
  if (payload instanceof FormData) {
    return payload;
  }

  return JSON.stringify(payload);
}

/**
 * Handle request errors
 */
function fetchErrorToNetworkError(
  error: unknown,
  searchInputs?: QueryParamData,
) {
  // Request failed to send or something failed while parsing the response
  // Log the JS error to support troubleshooting
  console.error(error);
  return searchInputs
    ? new NetworkError(error, searchInputs)
    : new NetworkError(error);
}

function handleNotOkResponse(
  response: APIResponse,
  url: string,
  searchInputs?: QueryParamData,
) {
  const { errors } = response;
  if (isEmpty(errors)) {
    // No detailed errors provided, throw generic error based on status code
    throwError(response, url, searchInputs);
  } else {
    if (errors) {
      const firstError = errors[0] as APIResponseError;
      throwError(response, url, searchInputs, firstError);
    }
  }
}

const throwError = (
  response: APIResponse,
  url: string,
  searchInputs?: QueryParamData,
  firstError?: APIResponseError,
) => {
  const { status_code, message } = response;
  console.error(
    `API request error at ${url} (${status_code}): ${message}`,
    searchInputs,
  );

  // Include just firstError for now, we can expand this
  // If we need ValidationErrors to be more expanded
  const error = firstError ? { message, firstError } : { message };
  switch (status_code) {
    case 400:
      throw new BadRequestError(error, searchInputs);
    case 401:
      throw new UnauthorizedError(error, searchInputs);
    case 403:
      throw new ForbiddenError(error, searchInputs);
    case 404:
      throw new NotFoundError(error, searchInputs);
    case 422:
      throw new ValidationError(error, searchInputs);
    case 408:
      throw new RequestTimeoutError(error, searchInputs);
    case 500:
      throw new InternalServerError(error, searchInputs);
    case 503:
      throw new ServiceUnavailableError(error, searchInputs);
    default:
      throw new ApiRequestError(
        error,
        "APIRequestError",
        status_code,
        searchInputs,
      );
  }
};
