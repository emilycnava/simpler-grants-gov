data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_ecr_repository" "app" {
  count = var.image_repository_name != null ? 1 : 0
  name  = var.image_repository_name
}

locals {
  alb_name                = var.service_name
  cluster_name            = var.service_name
  log_group_name          = "service/${var.service_name}"
  log_stream_prefix       = var.service_name
  task_executor_role_name = "${var.service_name}-task-executor"
  image_url               = var.image_repository_url != null ? "${var.image_repository_url}:${var.image_tag}" : "${data.aws_ecr_repository.app[0].repository_url}:${var.image_tag}"
  hostname                = var.hostname != null ? [{ name = "HOSTNAME", value = var.hostname }] : []

  base_environment_variables = concat([
    { name : "PORT", value : tostring(var.container_port) },
    { name : "AWS_REGION", value : data.aws_region.current.name },
    { name : "S3_BUCKET_ARN", value : aws_s3_bucket.general_purpose.arn },
  ], local.hostname)
  db_environment_variables = var.db_vars == null ? [] : [
    { name : "DB_HOST", value : var.db_vars.connection_info.host },
    { name : "DB_PORT", value : var.db_vars.connection_info.port },
    { name : "DB_USER", value : var.db_vars.connection_info.user },
    { name : "DB_NAME", value : var.db_vars.connection_info.db_name },
    { name : "DB_SCHEMA", value : var.db_vars.connection_info.schema_name },
  ]
  environment_variables = concat(
    local.base_environment_variables,
    local.db_environment_variables,
    [{ name : "DRAFTS_S3_BUCKET_ARN", value : aws_s3_bucket.draft_documents.arn }],
    [
      for name, value in var.extra_environment_variables :
      { name : name, value : value }
    ],
  )
}

#-------------------
# Service Execution
#-------------------

resource "aws_ecs_service" "app" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.cluster.arn
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_instance_count

  # Allow changes to the desired_count without differences in terraform plan.
  # This allows autoscaling to manage the desired count for us.
  lifecycle {
    ignore_changes = [desired_count]
  }

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.app.id]
  }

  dynamic "load_balancer" {
    for_each = var.enable_load_balancer ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.app_tg[0].arn
      container_name   = var.service_name
      container_port   = var.container_port
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  family             = var.service_name
  execution_role_arn = aws_iam_role.task_executor.arn
  task_role_arn      = aws_iam_role.app_service.arn

  container_definitions = jsonencode([
    {
      name                   = var.service_name,
      image                  = local.image_url,
      memory                 = var.memory,
      cpu                    = var.cpu,
      networkMode            = "awsvpc",
      essential              = true,
      readonlyRootFilesystem = var.readonly_root_filesystem,

      # Need to define all parameters in the healthCheck block even if we want
      # to use AWS's defaults, otherwise the terraform plan will show a diff
      # that will force a replacement of the task definition
      healthCheck = var.healthcheck_command != null ? {
        interval = 30,
        retries  = 3,
        timeout  = 5,
        command  = var.healthcheck_command
      } : null,
      environment = local.environment_variables,
      secrets     = var.secrets,
      portMappings = [
        {
          containerPort = var.container_port,
        }
      ],
      linuxParameters = var.drop_linux_capabilities ? {
        capabilities = {
          drop = ["ALL"]
        },
        initProcessEnabled = true
      } : null,
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.service_logs.name,
          "awslogs-region"        = data.aws_region.current.name,
          "awslogs-stream-prefix" = local.log_stream_prefix
        }
      }
    }
  ])

  cpu    = var.cpu
  memory = var.memory

  requires_compatibilities = ["FARGATE"]

  # Reference https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html
  network_mode = "awsvpc"
}

resource "aws_ecs_cluster" "cluster" {
  name = local.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
