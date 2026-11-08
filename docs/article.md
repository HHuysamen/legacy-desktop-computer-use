# Automating a legacy desktop app with Computer Use

[Read this article on henryhuysamen.com](https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/)

If you work in finance, you probably know this kind of application. To get a report, you choose it from a list, enter a date, click through a few screens and save a file. There is no useful API, MCP server or browser interface. The screen is the interface.

OpenAI's [Computer Use tool](https://developers.openai.com/api/docs/guides/tools-computer-use) lets a model interpret screenshots and request mouse and keyboard actions. Your program executes those actions, captures the updated screen and sends it back.

An AI Engineer can build an AI application around this loop. The application supplies the task, starts the desktop session, handles failures and checks the output. No interactive chat session is needed.

Using the demo desktop app, LedgerDesk, I started with three finance reports. I then added five record-handling workflows and two tasks in LibreOffice Calc and Writer. The expanded test covers ten tasks, each attempted ten times.

[Watch the demo](../examples/presentation/demo-narrated-v2.mp4)

This video illustrates automating interaction with a desktop application using systematic computer use.

## Let your program run the workflow

Your program decides when a task starts and what counts as success. The model decides which screen actions to take.

The workflow has six steps:

1. Receive a task request.
2. Start a controlled desktop session.
3. Send the task and a screenshot to the model.
4. Execute the permitted actions and repeat the screenshot loop.
5. When the model reports completion, collect and verify the output.
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

The driver checks the target application and focus, restricts input to its allowed desktop area, and accepts only the keys and text the workflow needs. Use a dedicated desktop session and allow only the inputs the workflow needs.

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

A separate verifier checks the saved work. For reports, it checks the CSV columns, amounts, row order, missing rows and duplicates. For record changes, it also checks that only the requested database values changed. The Office tasks check the saved CSV or document and preserve the original file. The model cannot call the verifier or inspect its expected-state calculations.

Each attempt starts with fresh data and an empty export folder. Old files cannot produce a false pass. Successful attempts keep their output; every attempt keeps the evidence available from the run, including a structured `run.json`, an HTML report, screenshots and an action trace.

Run the complete workflow from the command line:

```bash
python -m ledgerdesk run \
  --task overdue-invoices \
  --as-of 2026-10-15
```

The command returns zero only after verification passes. Failures return nonzero. An existing job runner could invoke it, process verified files and send failures for review. Scheduling is not part of this demo.

## Cost

I ran each of the ten tasks ten times with `gpt-6.1-terra`. **99 of the 100 attempts passed verification**, and all 99 successful outputs passed a separate recheck.

| Task | Verified runs | Median time | Average API cost |
| --- | ---: | ---: | ---: |
| Monthly revenue | 10 of 10 | 26.7 s | US$0.036 |
| Overdue invoices | 10 of 10 | 26.7 s | US$0.040 |
| Reconciliation exceptions | 10 of 10 | 25.3 s | US$0.036 |
| Invoice lookup | 10 of 10 | 25.3 s | US$0.046 |
| Customer contact update | 10 of 10 | 28.1 s | US$0.047 |
| Draft invoice entry | 10 of 10 | 31.8 s | US$0.047 |
| Receipt recording | 10 of 10 | 29.5 s | US$0.047 |
| CSV import | 10 of 10 | 26.1 s | US$0.046 |
| Calc sort and export | 9 of 10 | 57.5 s | US$0.117 |
| Writer text replacement | 10 of 10 | 35.7 s | US$0.042 |

The first Calc run stopped because my driver treated the Save As dialog as the complete allowed area. Its format dropdown extends below it. I corrected the boundary check; the next nine Calc attempts passed. That [failed attempt](../examples/evaluation-100/runs/20261108T125117-bdb21f/report.html) stays in the results.

The total model API estimate was **US$5.04**, or about **US$0.050 per attempt**, including the failure. At that average, one attempt each workday would cost roughly **US$1.01 for a 20-workday month**. A simple reporting task came out closer to US$0.71–0.80 per month; the Calc task about US$2.35. More complex workflows can need more screenshots and requests.

Times include starting the desktop and checking the output. Costs use [OpenAI's published standard rates](https://developers.openai.com/api/docs/pricing), excluding desktop hosting and other operating costs; actual billing may differ. The [full 100-run results](../examples/evaluation-100/index.html), [cost calculation](../examples/evaluation-100/cost-analysis.json) and [research and methodology](evaluation-methodology.md) show the tasks, fixed inputs, driver change and retained evidence.

A [follow-up study](https://www.henryhuysamen.com/demos/ledgerdesk/follow-up/) examines new input files and changed window layouts in Calc and Writer, separate stopping controls, and native GnuCash transactions. Its results and evidence are reported separately from the 100 attempts above.

## Applying this to your own application

Start with a contained workflow that produces something you can verify. Define its inputs, restrict the permitted actions and decide how to handle failure before you run it. If the app has a supported integration, use that first.

The [repository](https://github.com/HHuysamen/legacy-desktop-computer-use) contains the app, driver, agent loop and verifier, with setup instructions. Running the agent requires an OpenAI project with access to the model and computer tool.

Desktop applications with no APIs, MCP servers or browser interfaces can be navigated using programmatic computer use.
