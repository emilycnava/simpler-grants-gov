# docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc
data "aws_vpc" "network" {
  filter {
    name   = "tag:Name"
    values = [module.project_config.network_configs[var.environment_name].vpc_name]
  }
}

# docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.network.id]
  }
  filter {
    name   = "tag:subnet_type"
    values = ["private"]
  }
}

# docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.network.id]
  }
  filter {
    name   = "tag:subnet_type"
    values = ["public"]
  }
}

locals {
  # The prefix key/value pair is used for Terraform Workspaces, which is useful for projects with multiple infrastructure developers.
  # By default, Terraform creates a workspace named “default.” If a non-default workspace is not created this prefix will equal “default”,
  # if you choose not to use workspaces set this value to "dev"
  prefix = terraform.workspace == "default" ? "" : "${terraform.workspace}-"

  # Add environment specific tags
  tags = merge(module.project_config.default_tags, {
    environment = var.environment_name
    description = "Application resources created in ${var.environment_name} environment"
  })

  service_name = "${local.prefix}${module.app_config.app_name}-${var.environment_name}"

  is_temporary = startswith(terraform.workspace, "t-")

  environment_config = module.app_config.environment_configs[var.environment_name]
  service_config     = local.environment_config.service_config
}

terraform {
  required_version = "< 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.68.0"
    }
  }

  backend "s3" {
    encrypt = "true"
  }
}

provider "aws" {
  region = local.service_config.region
  default_tags {
    tags = local.tags
  }
}

module "project_config" {
  source = "../../project-config"
}

module "app_config" {
  source = "../app-config"
}

module "service" {
  source                = "../../modules/service"
  service_name          = local.service_name
  is_temporary          = local.is_temporary
  enable_load_balancer  = false
  image_repository_name = module.app_config.image_repository_name
  image_tag             = local.image_tag
  vpc_id                = data.aws_vpc.network.id
  public_subnet_ids     = data.aws_subnets.public.ids
  private_subnet_ids    = data.aws_subnets.private.ids
  cpu                   = 1024
  memory                = 2048

  # This is a task based service, not a web server, so we don't need to run any instances of the service at rest.
  desired_instance_count = 0

  extra_environment_variables = local.service_config.extra_environment_variables

  secrets = concat(
    [for secret_name in keys(local.service_config.secrets) : {
      name      = secret_name
      valueFrom = module.secrets[secret_name].secret_arn
    }],
  )
}
