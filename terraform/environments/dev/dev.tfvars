aws_region     = "us-west-2"
project_name   = "winter-injury-observatory"
environment    = "dev"
vpc_cidr       = "10.0.0.0/16"

availability_zones = [
  "us-west-2a",
  "us-west-2b"
]

database_name               = "winter_injury_observatory"
rds_instance_class          = "db.t3.micro"
rds_allocated_storage       = 20
rds_backup_retention_period = 7
