"""Tool for creating local cron-style jobs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.services.cron import upsert_cron_job, validate_cron_expression
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class CronCreateToolInput(BaseModel):
    """Arguments for cron job creation."""

    cron: str = Field(
        description="Standard 5-field cron expression in local time (e.g., '*/5 * * * *' for every 5 minutes)",
    )
    prompt: str = Field(description="The prompt to enqueue at each fire time")
    recurring: bool = Field(
        default=True,
        description="True = fire on every cron match until deleted or auto-expired after 180 days. False = fire once at the next match, then auto-delete.",
    )
    durable: bool = Field(
        default=False,
        description="True = persist to .illusion/scheduled_tasks.json and survive restarts. False = in-memory only, dies when session ends.",
    )


class CronCreateTool(BaseTool):
    """Create or replace a local cron job."""

    name = "cron_create"
    description = """Schedule a prompt to be enqueued at a future time. Use for both recurring schedules and one-shot reminders.

Uses standard 5-field cron in the user's local timezone: minute hour day-of-month month day-of-week. "0 9 * * *" means 9am local - no timezone conversion needed.

## One-shot tasks (recurring: false)

For "remind me at X" or "at <time>, do Y" requests - fire once then auto-delete.
Pin minute/hour/day-of-month/month to specific values:
  "remind me at 2:30pm today to check the deploy" -> cron: "30 14 <today_dom> <today_month> *", recurring: false
  "tomorrow morning, run the smoke test" -> cron: "57 8 <tomorrow_dom> <tomorrow_month> *", recurring: false

## Recurring jobs (recurring: true, the default)

For "every N minutes" / "every hour" / "weekdays at 9am" requests:
  "*/5 * * * *" (every 5 min), "0 * * * *" (hourly), "0 9 * * 1-5" (weekdays at 9am local)

## Avoid the :00 and :30 minute marks when the task allows it

Every user who asks for "9am" gets `0 9`, and every user who asks for "hourly" gets `0 *` - which means requests from across the planet land on the API at the same instant. When the user's request is approximate, pick a minute that is NOT 0 or 30:
  "every morning around 9" -> "57 8 * * *" or "3 9 * * *" (not "0 9 * * *")
  "hourly" -> "7 * * * *" (not "0 * * * *")
  "in an hour or so, remind me to..." -> pick whatever minute you land on, don't round

Only use minute 0 or 30 when the user names that exact time and clearly means it ("at 9:00 sharp", "at half past", coordinating with a meeting). When in doubt, nudge a few minutes early or late - the user will not notice, and the fleet will.

## Durability

By default (durable: false) the job lives only in this illusion session - nothing is written to disk, and the job is gone when illusion exits. Pass durable: true to write to .illusion/scheduled_tasks.json so the job survives restarts. Only use durable: true when the user explicitly asks for the task to persist ("keep doing this every day", "set this up permanently"). Most "remind me in 5 minutes" / "check back in an hour" requests should stay session-only.

## Runtime behavior

Jobs only fire while the REPL is idle (not mid-query). Durable jobs persist to .illusion/scheduled_tasks.json and survive session restarts - on next launch they resume automatically. One-shot durable tasks that were missed while the REPL was closed are surfaced for catch-up. Session-only jobs die with the process. The scheduler adds a small deterministic jitter on top of whatever you pick: recurring tasks fire up to 10% of their period late (max 15 min); one-shot tasks landing on :00 or :30 fire up to 90 s early. Picking an off-minute is still the bigger lever.

Recurring tasks auto-expire after 180 days - they fire one final time, then are deleted. This bounds session lifetime. Tell the user about the 180-day limit when scheduling recurring jobs.

Returns a job ID you can pass to CronDelete."""
    input_model = CronCreateToolInput

    async def execute(
        self,
        arguments: CronCreateToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        if not validate_cron_expression(arguments.cron):
            return ToolResult(
                output=(
                    f"Invalid cron expression: {arguments.cron!r}\n"
                    "Use standard 5-field format: minute hour day month weekday\n"
                    "Examples: '*/5 * * * *' (every 5 min), '0 9 * * 1-5' (weekdays 9am)"
                ),
                is_error=True,
            )

        job_id = upsert_cron_job(
            {
                "schedule": arguments.cron,
                "prompt": arguments.prompt,
                "recurring": arguments.recurring,
                "durable": arguments.durable,
                "cwd": str(context.cwd),
            }
        )
        kind = "recurring" if arguments.recurring else "one-shot"
        persist = "durable" if arguments.durable else "session-only"
        return ToolResult(
            output=f"Created {kind} cron job '{job_id}' [{arguments.cron}] ({persist})"
        )
