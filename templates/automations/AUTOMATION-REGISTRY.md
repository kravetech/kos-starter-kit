# Automation Registry

## Daily Review

Name: Daily review  
Status: Manual  
Type: Review  
Trigger: Time or explicit request  
Frequency: Daily at {{daily_review_time}}  
Owner: {{preferred_name}}  
Execution tool: Obsidian or approved agent  
Inputs: Schedule, Inbox, active handoffs  
Outputs: Updated daily note and next actions  
Dependencies: None  
Privacy level: Internal  
Failure behavior: Record failure; do not silently reschedule commitments  
Last validated: Not validated  
Instructions: Review overdue work, tomorrow, blockers, and one critical priority.

## Weekly Review

Name: Weekly review  
Status: Manual  
Type: Review  
Trigger: Explicit request  
Frequency: {{weekly_review_day}}  
Owner: {{preferred_name}}  
Execution tool: Obsidian or approved agent  
Inputs: Active projects, schedule, inbox, handoffs  
Outputs: Weekly review note  
Dependencies: None  
Privacy level: Internal  
Failure behavior: Leave state unchanged and report missing inputs  
Last validated: Not validated  
Instructions: Review outcomes, commitments, project health, Git status, memory, and handoffs.

## Monthly Review

Name: Monthly review  
Status: Manual  
Type: Review  
Trigger: Explicit request  
Frequency: Monthly  
Owner: {{preferred_name}}  
Execution tool: Obsidian or approved agent  
Inputs: Weekly reviews and domain MOCs  
Outputs: Monthly review note  
Dependencies: None  
Privacy level: Internal  
Failure behavior: Report incomplete coverage  
Last validated: Not validated  
Instructions: Review system health, priorities, archive candidates, and durable changes.

## Inbox Processing

Name: Inbox processing  
Status: Manual  
Type: Maintenance  
Trigger: Explicit request  
Frequency: Daily  
Owner: {{preferred_name}}  
Execution tool: Obsidian or approved agent  
Inputs: `06 - Inbox`  
Outputs: Routed items  
Dependencies: Domain MOCs  
Privacy level: Internal  
Failure behavior: Preserve ambiguous items in Inbox  
Last validated: Not validated  
Instructions: Classify, route, and preserve source/privacy context.

## Context Maintenance

Name: Memory and handoff maintenance  
Status: Manual  
Type: Maintenance  
Trigger: Project phase change or size threshold  
Frequency: Weekly and on phase changes  
Owner: {{preferred_name}}  
Execution tool: Approved agent  
Inputs: Root and selected project context  
Outputs: Compact current context and optional history snapshot  
Dependencies: Human review for durable memory  
Privacy level: Internal  
Failure behavior: Do not rewrite when authority or approval is unclear  
Last validated: Not validated  
Instructions: Keep memory durable and handoff current; archive meaningful prior state.

## Project Health

Name: Active-project health check  
Status: Manual  
Type: Validation  
Trigger: Explicit request  
Frequency: Weekly  
Owner: {{preferred_name}}  
Execution tool: Approved agent  
Inputs: Active project indexes and context  
Outputs: Findings and next action  
Dependencies: None  
Privacy level: Internal  
Failure behavior: Report warnings separately from failures  
Last validated: Not validated  
Instructions: Check ownership, objective, blockers, next action, and stale context.

## Repository Maintenance

Name: Broken-link validation and Git status review  
Status: Manual  
Type: Validation  
Trigger: Before structural change  
Frequency: Weekly or before commit  
Owner: {{preferred_name}}  
Execution tool: Git and validation scripts  
Inputs: Markdown links and repository status  
Outputs: Findings  
Dependencies: Git optional  
Privacy level: Internal  
Failure behavior: Never weaken validation or discard unrelated changes  
Last validated: Not validated  
Instructions: Report exact broken links and classify existing vs. introduced changes.

## Backup Reminder

Name: Backup reminder  
Status: Manual  
Type: Reminder  
Trigger: Explicit schedule  
Frequency: Weekly  
Owner: {{preferred_name}}  
Execution tool: User-selected  
Inputs: Backup policy  
Outputs: Confirmation record  
Dependencies: Backup destination configured separately  
Privacy level: Restricted  
Failure behavior: Report missing configuration  
Last validated: Not validated  
Instructions: Verify a recoverable backup; never claim success without evidence.

## External Integrations

The following definitions all start with `Status: Not configured`:

### Content Planning
Name: Content planning  
Status: Not configured  
Type: External workflow  
Trigger: Not configured  
Frequency: Not configured  
Owner: {{preferred_name}}  
Execution tool: Not configured  
Inputs: Approved content backlog  
Outputs: Draft plan  
Dependencies: Explicit connector configuration  
Privacy level: Internal  
Failure behavior: No action  
Last validated: Not validated  
Instructions: Configure explicitly before use.

### Email Attention Scan
Name: Email attention scan  
Status: Not configured  
Type: External integration  
Trigger: Not configured  
Frequency: Not configured  
Owner: {{preferred_name}}  
Execution tool: Gmail connector  
Inputs: Bounded mailbox query  
Outputs: Attention summary  
Dependencies: Explicit authorization  
Privacy level: Restricted  
Failure behavior: No mailbox changes  
Last validated: Not validated  
Instructions: Never send, archive, delete, or label without explicit authorization.

### Calendar Preparation
Name: Calendar preparation  
Status: Not configured  
Type: External integration  
Trigger: Not configured  
Frequency: Not configured  
Owner: {{preferred_name}}  
Execution tool: Calendar connector  
Inputs: Bounded event window  
Outputs: Preparation brief  
Dependencies: Explicit authorization  
Privacy level: Restricted  
Failure behavior: No calendar changes  
Last validated: Not validated  
Instructions: Read-only until a write is explicitly requested.

### Financial Summary
Name: Financial summary  
Status: Not configured  
Type: External integration  
Trigger: Not configured  
Frequency: Not configured  
Owner: {{preferred_name}}  
Execution tool: Not configured  
Inputs: Explicitly selected records  
Outputs: Draft summary  
Dependencies: Explicit authorization and source policy  
Privacy level: Restricted  
Failure behavior: No action  
Last validated: Not validated  
Instructions: Do not infer access or move financial data.

### External-Source Synchronization
Name: External-source synchronization  
Status: Not configured  
Type: External integration  
Trigger: Not configured  
Frequency: Not configured  
Owner: {{preferred_name}}  
Execution tool: Provider-specific connector  
Inputs: Explicit source registry  
Outputs: Generated inventory and bounded summary  
Dependencies: Read-only provider configuration  
Privacy level: Restricted  
Failure behavior: Preserve source; report partial results  
Last validated: Not validated  
Instructions: Inventory read-only; exclude generated raw data from normal AI context and Git.
