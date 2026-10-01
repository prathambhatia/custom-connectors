---
name: aws-connector
description: ALWAYS use this instead of any AWS MCP whenever AWS is mentioned — SSO login, SSM Session Manager tunnels and Run Command, Parameter Store, CloudWatch logs and Logs Insights, ECS services/tasks/deploys/exec, ECR, RDS, ElastiCache, Secrets Manager, S3, EC2, ALB, CloudFront, Lambda, SQS/SNS, DynamoDB, Route53, ACM, IAM, CloudTrail, Cost Explorer — via the aws CLI and your own AWS profiles. Triggers on "aws", "tunnel into RDS", "check the logs", "ecs", "restart the service", "what is deployed", "secrets", "ssm", "s3", "cloudfront", "aws bill". Sets itself up on first use.
user-invocable: true
argument-hint: "profile/env + what to do"
---

# AWS via the CLI (no MCP)

The `aws` CLI already covers every AWS API, so this skill is a map of the commands that matter plus
the traps, not a wrapper. Everything runs as **your** AWS login.

## First run: setup (do this automatically)

1. `aws --version`. If missing, tell the user: `brew install awscli`.
2. `aws configure list-profiles`. For each profile: `aws sts get-caller-identity --profile <p> --query '[Account,Arn]' --output text`.
   - `Token has expired` / `SSO session` errors → ask the user to run `! aws sso login --profile <p>` (opens a browser).
   - No profiles → ask with exactly this one line:
     > Please give your AWS SSO start URL and region from here: your AWS access portal link (from DevOps), e.g. https://xxxx.awsapps.com/start
     then have them run `! aws configure sso`.
3. Show a table of profile → account → role (from the ARN, e.g. `AdministratorAccess` vs `ReadOnlyAccess`),
   and remember it for the session. **Note which profiles are read-only**: they can't read secret
   values, start SSM sessions or write anything.
4. For SSM tunnels: `which session-manager-plugin`, else `brew install --cask session-manager-plugin`.
5. If a `default` profile has static keys for an account they don't recognise, point it out and
   always pass `--profile` explicitly.

## Safety

- **Writes to anything production need two separate confirmations** from the user, the second one
  saying plainly that it changes production. Reads (`describe/list/get`, tailing logs, opening a
  tunnel to look) don't.
- Secret values (`get-secret-value`, `get-parameter --with-decryption`) go to a file, never into chat.
- Never kill a tunnel or session you didn't open.

## SSM (Systems Manager): tunnels, commands, parameters

SSM is an AWS API and works fully from the CLI. Find instances that SSM can reach:
`aws ssm describe-instance-information --profile <p> --query 'InstanceInformationList[].[InstanceId,PingStatus,ComputerName]' --output text`.
Get a DB/Redis endpoint: `aws rds describe-db-instances --query 'DBInstances[].[DBInstanceIdentifier,Endpoint.Address,Endpoint.Port]'`,
`aws elasticache describe-cache-clusters --show-cache-node-info`.

```bash
# port-forward a private RDS/Redis through an SSM-managed instance (pick a free local port: lsof -ti :5434)
aws ssm start-session --profile <p> --target <instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<endpoint>"],"portNumber":["5432"],"localPortNumber":["5434"]}' &
sleep 6; nc -z localhost 5434 && echo up
pkill -f 'localPortNumber.*"5434"'          # close it when done
# run a command on an instance
C=$(aws ssm send-command --profile <p> --instance-ids <id> --document-name AWS-RunShellScript \
  --parameters 'commands=["uptime"]' --query Command.CommandId --output text); sleep 4
aws ssm get-command-invocation --profile <p> --command-id $C --instance-id <id> --query '[Status,StandardOutputContent]' --output text
# interactive shell: the user runs  ! aws ssm start-session --target <id> --profile <p>
# Parameter Store
aws ssm describe-parameters --profile <p>
aws ssm get-parameters-by-path --path /app/uat --recursive --profile <p> --query 'Parameters[].Name'
aws ssm get-parameter --name <name> --with-decryption --profile <p> --query Parameter.Value --output text > /tmp/p.txt
```

`AccessDeniedException` on `StartSession` = the role is read-only; fall back to SSH via the jump
host if they have a key, or ask their DevOps.

## CLI reference

Always `--profile <p>` (and `--region` if not set in the profile). Use `--query` and
`--output text` to keep output small; save big JSON to a file. **Anything not listed is still
available:** `aws <service> help` and `aws <service> <command> help` list every command.

**Copy commands from this table exactly; check flags with `aws <service> <command> help` instead of guessing.**

| Service | Read | Common writes (prod-write rule on admin profiles) |
|---|---|---|
| **Identity** | `aws sts get-caller-identity` | |
| **ECS** | `ecs list-clusters`; `list-services --cluster C`; `describe-services --cluster C --services S --query 'services[0].[status,runningCount,desiredCount,taskDefinition,deployments]'`; `list-tasks --cluster C --service-name S`; `describe-tasks`; `describe-task-definition --task-definition S` | redeploy: `ecs update-service --cluster C --service S --force-new-deployment`; scale: `--desired-count N`; stop a task: `ecs stop-task`; wait: `aws ecs wait services-stable --cluster C --services S` (untested writes) |
| **ECS Exec** (shell in a container) | only on services with `enableExecuteCommand=true` (check `describe-services`) | `aws ecs execute-command --cluster C --task T --container <name> --interactive --command "/bin/sh"`; needs a TTY, so the user runs it with `!` (untested) |
| **ECR** | `ecr describe-repositories`; `describe-images --repository-name R` | |
| **RDS** | `rds describe-db-instances`; `describe-db-snapshots --db-instance-identifier I`; `describe-events --source-type db-instance --duration 1440` | `create-db-snapshot` (untested) |
| **ElastiCache** | `elasticache describe-cache-clusters --show-cache-node-info` | |
| **CloudWatch Logs** | `logs describe-log-groups`; `logs tail <group> --since 10m [--follow] [--filter-pattern error]`; `logs filter-log-events --log-group-name G --start-time <ms> --filter-pattern error` | |
| **Logs Insights** | `Q=$(aws logs start-query --log-group-name G --start-time <s> --end-time <s> --query-string '<query>' --query queryId --output text)`; `sleep 4; aws logs get-query-results --query-id $Q` | |
| **CloudWatch metrics/alarms** | `cloudwatch get-metric-statistics --namespace AWS/ECS --metric-name CPUUtilization --dimensions Name=ClusterName,Value=C Name=ServiceName,Value=S --start-time … --end-time … --period 300 --statistics Average`; `cloudwatch describe-alarms --state-value ALARM` | |
| **Secrets Manager** | `secretsmanager list-secrets`; `describe-secret --secret-id N`; `get-secret-value --secret-id N` (admin only; value to file, never chat) | `put-secret-value` (untested) |
| **S3** | `s3 ls`; `s3 ls s3://bucket/prefix/`; `s3 cp s3://b/k ./`; `s3api head-object` | `s3 cp ./f s3://b/k`, `s3 sync`, `s3 rm` (untested) |
| **EC2 / VPC** | `ec2 describe-instances --query 'Reservations[].Instances[].[Tags[?Key==`Name`]\|[0].Value,InstanceId,State.Name,PublicIpAddress]'`; `describe-security-groups`; `describe-vpcs` | start/stop/reboot-instances (untested) |
| **Load balancers** | `elbv2 describe-load-balancers`; `describe-target-groups`; `describe-target-health --target-group-arn A` | |
| **CloudFront** | `cloudfront list-distributions --query 'DistributionList.Items[].[Id,DomainName,Aliases.Items[0]]'` | `cloudfront create-invalidation --distribution-id D --paths '/*'` (untested) |
| **Lambda** | `lambda list-functions`; `get-function --function-name F` | `lambda invoke --function-name F out.json` (untested) |
| **SQS / SNS** | `sqs list-queues`; `sqs get-queue-attributes --queue-url U --attribute-names All`; `sns list-topics` | `sqs purge-queue` (destructive, untested) |
| **DynamoDB** | `dynamodb list-tables`; `describe-table --table-name T`; `scan --table-name T --max-items 5` | |
| **EventBridge** | `events list-rules` | |
| **Route53 / ACM** | `route53 list-hosted-zones`; `acm list-certificates` | |
| **API Gateway** | `apigatewayv2 get-apis` | |
| **IAM** | `iam list-roles`; `iam get-role --role-name R` | |
| **CloudTrail** (who did what) | `cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=UpdateService --max-results 10` | |
| **Cost Explorer** | `ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity MONTHLY --metrics UnblendedCost`; add `--group-by Type=DIMENSION,Key=SERVICE` for per-service | |

**Traps**

- **A `| head` or `| jq` after an AWS command hides its failure**: the pipe succeeds even when the
  call was `AccessDenied`. Check stderr, or run unpiped first.
- `list-*` on the wrong profile/region returns **empty, not an error**. Empty means "check the
  profile and region" before "nothing's there".
- Apps often log their own `env` field wrong (a UAT app logging `"env":"production"`). Trust the
  log group and profile, not the message body.
- AWS times are UTC; convert to the user's timezone.
- Two accounts can have resources with identical names (`app-uat-db` in both). The profile decides.

**How to apply:** use the aws CLI through this skill for every AWS request, even if an AWS MCP is
connected. Don't call its tools.
