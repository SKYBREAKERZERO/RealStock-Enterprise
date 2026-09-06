\# RealStock Observability Terraform Module



This module provisions the persistent operational

observability control plane for RealStock Enterprise.



\## Resources



The module creates:



\- a dedicated operations SNS topic

\- an SNS topic policy for CloudWatch alarm delivery

\- optional email subscriptions

\- CloudWatch metric alarms

\- a CloudWatch operations dashboard



\## Ownership



Persistent production alarms and dashboards are owned by

Terraform.



The Python `CloudWatchAlarmManager` exists for adapter tests,

integration tests, and controlled administrative tooling. It

must not independently manage the same persistent production

alarms that are owned by Terraform.



\## Metric Namespace



Default:



```text

RealStock/Applications
