# We won't delete the KMS key, but we will mark it as no longer in use.
# We don't delete it because that would violate an AWS security best practice.
#
# For future historians: this KMS key was used in service of AWS DMS.
# It it no longer in use because we have a new way to sync data between our databases.
resource "aws_kms_key" "dms_endpoints" {
  # checkov:skip=CKV_AWS_227: KMS key is intentionally disabled
  description         = "NO LONGER IN USE"
  enable_key_rotation = true
  is_enabled          = false
  # checkov:skip=CKV2_AWS_64:TODO: https://github.com/HHS/simpler-grants-gov/issues/2366
}
