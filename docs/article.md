# Automating a legacy desktop app with Computer Use

[Read this article on henryhuysamen.com](https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/)

If you work in finance, you probably know this kind of application. To get a report, you choose it from a list, enter a date, click through a few screens and save a file. There is no useful API, MCP server or browser interface. The screen is the interface.

OpenAI's [Computer Use tool](https://developers.openai.com/api/docs/guides/tools-computer-use) lets a model interpret screenshots and request mouse and keyboard actions. Your program executes those actions, captures the updated screen and sends it back.

An AI Engineer can build an AI application around this loop. The application supplies the task, starts the desktop session, handles failures and checks the output. No interactive chat session is needed.

Using the demo desktop app, LedgerDesk, I tested this approach on three finance reports. The runner operates the app, collects the exported CSV and checks it against known answers.

[Watch the demo](../examples/presentation/demo-narrated-v2.mp4)

This video illustrates automating interaction with a desktop application using systematic computer use.

## Let your program run the workflow

Your program decides when a task starts and what counts as success. The model decides which screen actions to take.

The workflow has six steps:

1. Receive a report request.
2. Start a controlled desktop session.
3. Send the task and a screenshot to the model.
4. Execute the permitted actions and repeat the screenshot loop.
5. When the model reports completion, collect and verify the CSV.
6. Return the verified file, or a failure result with the available evidence.

The loop stops on completion, a limit, a safety check or an error. The legacy application needs no changes: the controller calls the model provider's API, while the app receives ordinary mouse clicks and keystrokes.

For this demo, the app runs as a native Tkinter window on a Linux desktop in Docker. A browser viewer lets me watch. It supplies no DOM or control interface to the model.

## Start with one clear task

Choose a workflow with defined inputs and an output you can check. One request in the demo is:

> Generate monthly revenue for September 2026, excluding voided invoices, and export the result as a CSV.

The app calculates the report. The agent finds the controls, enters the month and saves the file. The accounting stays inside the application.

The data is synthetic, with partially paid invoices, date boundaries and one-cent differences included to make mistakes detectable.

## Give the model a desktop driver

The driver connects the model to the computer. It captures screenshots and implements click, type, keypress and scroll.

Here, [DesktopDriver](https://github.com/HHuysamen/legacy-desktop-computer-use/blob/main/ledgerdesk/desktop_driver.py) sends these operations to the isolated guest, where PyAutoGUI applies them. The model picks coordinates from screenshots. It cannot inspect widgets, run SQL or call a hidden export command.

The driver checks the target window and focus, rejects coordinates outside it, and restricts accepted keys and text. Use a dedicated desktop session and allow only the inputs the workflow needs.

## Call Computer Use from Python

The [agent is a function](https://github.com/HHuysamen/legacy-desktop-computer-use/blob/main/ledgerdesk/computer_agent.py). After starting a fresh desktop and preparing a directory for the run, the controller calls it:

```python
from ledgerdesk.computer_agent import run_agent
from ledgerdesk.desktop_driver import DesktopDriver
from ledgerdesk.tasks import task_instruction

result = run_agent(
    driver=DesktopDriver(run_dir),
    instruction=task_instruction("monthly-revenue"),
    run_dir=run_dir,
    model="gpt-6.1-terra",
    max_requests=20,
    max_actions=40,
    timeout_seconds=300,
    budget_usd=2.0,
)
```

`run_dir` is the prepared directory. This function handles the agent; the full runner also starts the desktop, collects the export and verifies it.

Inside the function, the OpenAI Responses API receives the task and screenshot history with the computer tool enabled. The central calls are:

```python
computer = ComputerToolset(driver)

response = client.responses.create(
    model=model,
    input=history,
    tools=[{"type": "computer"}],
    store=False,
)

# For each computer call returned by the model:
tool_output = computer.execute(
    computer_call,
    before_action=before_action,
)
```

The loop saves the response and sends the resulting screenshot back with the conversation history. A screenshot can follow a batch of actions, rather than every click.

These excerpts are not standalone scripts. The repository contains the full loop, including history handling, usage records, limits and cleanup. The [OpenAI driver documentation](https://developers.openai.com/api/docs/guides/tools-computer-use-sdk-drivers#computer-driver-contract) describes the SDK interface.

## Check the result

The model saying it is finished does not make the file correct.

A separate verifier compares the exported CSV with results computed independently from the demo data. It checks columns, amounts, row order, missing rows and duplicates. The model cannot call it or see its answers.

Each attempt starts with fresh data and an empty export folder. Old files cannot produce a false pass. Successful attempts keep the CSV; every attempt keeps the evidence available from the run, including a structured `run.json`, an HTML report, screenshots and an action trace.

Run the complete workflow from the command line:

```bash
python -m ledgerdesk run \
  --task overdue-invoices \
  --as-of 2026-10-15
```

The command returns zero only after verification passes. Failures return nonzero. An existing job runner could invoke it, process verified files and send failures for review. Scheduling is not part of this demo.

## Cost

I ran each of the three reports eight times with `gpt-6.1-terra`. All **24 exports** passed verification and an independent recheck.

| Report | Verified runs | Average model API cost |
| --- | ---: | ---: |
| Monthly revenue | 8 of 8 | US$0.036 |
| Overdue invoices | 8 of 8 | US$0.039 |
| Reconciliation exceptions | 8 of 8 | US$0.036 |

The total estimate was **US$0.88**, or about **US$0.037 per run**. At that average, running one similar task each workday would cost roughly **US$0.73 for a 20-workday month**. More complex workflows that need additional screenshots and model requests will cost more.

These figures estimate model API usage at [OpenAI's published standard rates](https://developers.openai.com/api/docs/pricing). They exclude desktop hosting and other operating costs; actual billing may differ. The [full 24-run results](../examples/evaluation-24/index.html) and [cost calculation](../examples/evaluation-24/cost-analysis.json) retain the measurements and evidence.

## Applying this to your own application

Start with a contained workflow that produces something you can verify. Define its inputs, restrict the permitted actions and decide how to handle failure before you run it. If the app has a supported integration, use that first.

The [repository](https://github.com/HHuysamen/legacy-desktop-computer-use) contains the app, driver, agent loop and verifier, with setup instructions. Running the agent requires an OpenAI project with access to the model and computer tool.

Desktop applications with no APIs, MCP servers or browser interfaces can be navigated using programmatic computer use.
