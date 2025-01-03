import logging

from src.api import response
from src.api.route_utils import raise_flask_error
from src.api.users import user_schemas
from src.api.users.user_blueprint import user_blueprint
from src.auth.api_key_auth import api_key_auth

logger = logging.getLogger(__name__)


@user_blueprint.post("/token")
@user_blueprint.input(
    user_schemas.UserTokenHeaderSchema, location="headers", arg_name="x_oauth_login_gov"
)
@user_blueprint.output(user_schemas.UserTokenResponseSchema)
@user_blueprint.auth_required(api_key_auth)
def user_token(x_oauth_login_gov: dict) -> response.ApiResponse:
    logger.info("POST /v1/users/token")

    if x_oauth_login_gov:
        data = {
            "token": "the token goes here!",
            "user": {
                "user_id": "abc-...",
                "email": "example@gmail.com",
                "external_user_type": "login_gov",
            },
            "is_user_new": True,
        }
        return response.ApiResponse(message="Success", data=data)

    message = "Missing X-OAuth-login-gov header"
    logger.info(message)

    raise_flask_error(400, message)
