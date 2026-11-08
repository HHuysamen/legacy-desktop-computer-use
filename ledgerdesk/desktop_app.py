"""LedgerDesk's native reporting window. No automation interface is exposed."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import tkinter as tk
from tkinter import ttk

from . import reports
from .seed_data import reset_database


WINDOW_TITLE = "LedgerDesk — Demo Finance"


def write_csv_export(
    export_dir: Path,
    report_id: str,
    headers: list[str],
    rows: list[dict[str, str]],
) -> Path:
    """Save a completed preview under an application-controlled filename."""
    from .workflows import WORKFLOWS
    if report_id not in reports.REPORTS and report_id not in WORKFLOWS:
        raise ValueError("Unknown report")
    export_dir = Path(export_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    destination = export_dir / f"{report_id}.csv"
    # Replacing a temporary file never follows an existing destination symlink.
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=export_dir, delete=False
        ) as stream:
            temporary = stream.name
            writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return destination


class LedgerDesk(tk.Tk):
    def __init__(self, db_path: Path, export_dir: Path) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.export_dir = Path(export_dir)
        self.title(WINDOW_TITLE)
        self.geometry("1100x760+35+35")
        self.resizable(False, False)
        self.configure(background="#e7e7e2")
        self._result: tuple[str, list[str], list[dict[str, str]]] | None = None
        self._parameter_signature: tuple[str, str, str, str] | None = None
        self.report_name = tk.StringVar(value="Choose a report…")
        self.month = tk.StringVar(value="")
        self.as_of = tk.StringVar(value="")
        self.tolerance = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready. Select a report, then click Run Report.")
        self.summary = tk.StringVar(value="No report has been run.")
        self._configure_style()
        self._build_menu()
        self._build_window()
        for variable in (self.month, self.as_of, self.tolerance):
            variable.trace_add("write", self._parameters_changed)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("DejaVu Sans", 11))
        style.configure("TFrame", background="#e7e7e2")
        style.configure("TLabel", background="#e7e7e2", foreground="#202c36")
        style.configure("TLabelframe", background="#e7e7e2", borderwidth=1)
        style.configure("TLabelframe.Label", background="#e7e7e2", foreground="#293d50")
        style.configure("TButton", padding=(12, 7))
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)
        style.configure("Treeview", rowheight=28, font=("DejaVu Sans", 10), background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("DejaVu Sans", 10, "bold"), padding=6)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label="About LedgerDesk",
            command=lambda: self.status.set("LedgerDesk 1.0 · Fictional finance application · All records are synthetic."),
        )
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _build_window(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = tk.Frame(self, bg="#293d50", height=78)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)
        tk.Label(header, text="LedgerDesk", font=("DejaVu Sans", 23, "bold"), bg="#293d50", fg="white").pack(side="left", padx=22)
        tk.Label(header, text="FINANCE REPORTING\nNORTHSTAR DEMO COMPANY", justify="right", font=("DejaVu Sans", 10), bg="#293d50", fg="#d7e3ed").pack(side="right", padx=22)

        body = ttk.Frame(self, padding=(20, 15, 20, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        top = ttk.Frame(body)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(top, text="Reporting console", font=("DejaVu Sans", 15, "bold")).pack(side="left")
        ttk.Label(top, text="DEMO DATA  /  USD", foreground="#596774").pack(side="right")

        parameters = ttk.LabelFrame(body, text=" 1. Report and parameters ", padding=(15, 10))
        parameters.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(parameters, text="Report:").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.report_selector = ttk.Combobox(
            parameters,
            textvariable=self.report_name,
            state="readonly",
            values=list(reports.REPORTS.values()),
            width=49,
        )
        self.report_selector.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(12, 22), pady=(0, 10))
        self.report_selector.bind("<<ComboboxSelected>>", self._report_changed)
        ttk.Label(parameters, text="Month (YYYY-MM):").grid(row=1, column=0, sticky="w")
        self.month_entry = ttk.Entry(parameters, textvariable=self.month, width=14, state="disabled")
        self.month_entry.grid(row=1, column=1, sticky="w", padx=(12, 22))
        ttk.Label(parameters, text="As of (YYYY-MM-DD):").grid(row=1, column=2, sticky="w")
        self.as_of_entry = ttk.Entry(parameters, textvariable=self.as_of, width=14, state="disabled")
        self.as_of_entry.grid(row=1, column=3, sticky="w", padx=(12, 22))
        tolerance_box = ttk.Frame(parameters)
        tolerance_box.grid(row=1, column=4, sticky="e")
        ttk.Label(tolerance_box, text="Tolerance (USD):").pack(side="left", padx=(0, 8))
        self.tolerance_entry = ttk.Entry(tolerance_box, textvariable=self.tolerance, width=7, state="disabled")
        self.tolerance_entry.pack(side="left")
        self.run_button = ttk.Button(parameters, text="Run Report", command=self._run_report)
        self.run_button.grid(row=0, column=4, sticky="e", pady=(0, 10))
        parameters.columnconfigure(1, weight=1)
        parameters.columnconfigure(3, weight=1)

        preview = ttk.LabelFrame(body, text=" 2. Report preview ", padding=(12, 10))
        preview.grid(row=2, column=0, sticky="nsew")
        ttk.Label(preview, textvariable=self.summary).pack(anchor="w", pady=(0, 10))
        table_frame = ttk.Frame(preview)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, show="headings", columns=("empty",), selectmode="browse", height=6)
        self.table.heading("empty", text="Run a report to display results")
        self.table.column("empty", width=950, stretch=True)
        self.table.tag_configure("alternate", background="#f0f3f5")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        action_row = ttk.Frame(body)
        action_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(action_row, text="Exports contain only the rows in the current preview.", foreground="#596774").pack(side="left")
        self.export_button = ttk.Button(action_row, text="Export CSV…", command=self._show_export, state="disabled")
        self.export_button.pack(side="right")

        self.export_panel = ttk.LabelFrame(body, text=" 3. Confirm CSV export ", padding=(12, 10))
        self.export_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.export_filename = tk.StringVar(value="Review the preview, then click Export CSV.")
        ttk.Label(self.export_panel, textvariable=self.export_filename, font=("DejaVu Sans", 11, "bold")).pack(side="left")
        self.save_button = ttk.Button(self.export_panel, text="Save CSV", command=self._save_export, state="disabled")
        self.save_button.pack(side="right", padx=(8, 0))
        self.cancel_button = ttk.Button(self.export_panel, text="Cancel", command=self._hide_export, state="disabled")
        self.cancel_button.pack(side="right")

        footer = tk.Frame(self, background="#d5dadc", height=34)
        footer.grid(row=2, column=0, sticky="ew")
        footer.pack_propagate(False)
        tk.Label(footer, textvariable=self.status, background="#d5dadc", foreground="#233440", font=("DejaVu Sans", 10), anchor="w").pack(side="left", fill="x", expand=True, padx=18)

    def _report_id(self) -> str | None:
        return next((key for key, name in reports.REPORTS.items() if name == self.report_name.get()), None)

    def _signature(self) -> tuple[str, str, str, str]:
        return (self.report_name.get(), self.month.get(), self.as_of.get(), self.tolerance.get())

    def _report_changed(self, _event: object = None) -> None:
        report_id = self._report_id()
        self.month_entry.configure(state="normal" if report_id == "monthly-revenue" else "disabled")
        self.as_of_entry.configure(state="normal" if report_id == "overdue-invoices" else "disabled")
        self.tolerance_entry.configure(state="normal" if report_id == "reconciliation-exceptions" else "disabled")
        self._clear_preview()
        self.status.set("Parameters ready. Click Run Report to generate a preview.")

    def _parameters_changed(self, *_args: object) -> None:
        if self._result is not None:
            self._clear_preview()
            self.status.set("Parameters changed. Run the report again before exporting.")

    def _clear_preview(self) -> None:
        self._result = None
        self._parameter_signature = None
        self.table.delete(*self.table.get_children())
        self.export_button.configure(state="disabled")
        self.summary.set("No current preview. Click Run Report.")
        self._hide_export()

    def _run_report(self) -> None:
        report_id = self._report_id()
        if report_id is None:
            self.status.set("Select a report from the Report list first.")
            self.report_selector.focus_set()
            return
        try:
            headers, rows = reports.build_report(
                self.db_path,
                report_id,
                month=self.month.get(),
                as_of=self.as_of.get(),
                tolerance=self.tolerance.get(),
            )
        except (ValueError, OSError, sqlite3.Error) as error:
            self._clear_preview()
            self.status.set(f"Report could not run: {error}")
            return
        self._hide_export()
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=headers)
        for heading in headers:
            label = heading.replace("_", " ").title()
            self.table.heading(heading, text=label)
            width = max(140, 950 // max(1, len(headers)))
            self.table.column(heading, width=width, minwidth=120, stretch=True, anchor="w")
        for index, row in enumerate(rows):
            self.table.insert("", "end", values=[row[heading] for heading in headers], tags=("alternate",) if index % 2 else ())
        self._result = (report_id, headers, rows)
        self._parameter_signature = self._signature()
        self.summary.set(f"{self.report_name.get()}  ·  {len(rows)} rows  ·  USD")
        self.export_button.configure(state="normal")
        self.status.set(f"Report complete. {len(rows)} rows ready for review and CSV export.")

    def _show_export(self) -> None:
        if self._result is None or self._parameter_signature != self._signature():
            return
        self.export_filename.set(f"File: {self._result[0]}.csv  ·  {len(self._result[2])} rows")
        self.save_button.configure(state="normal")
        self.cancel_button.configure(state="normal")
        self.status.set("Confirm export with Save CSV. An existing file with this name will be replaced.")

    def _hide_export(self) -> None:
        self.export_filename.set("Review the preview, then click Export CSV.")
        self.save_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")

    def _save_export(self) -> None:
        if self._result is None or self._parameter_signature != self._signature():
            self.status.set("Run the report again before exporting.")
            self._hide_export()
            return
        report_id, headers, rows = self._result
        try:
            output = write_csv_export(self.export_dir, report_id, headers, rows)
        except OSError as error:
            self.status.set(f"Export failed: {error}")
            return
        self._hide_export()
        self.status.set(f"Export complete: {output.name}  ·  {len(rows)} rows saved.")


def main(db_path: Path, export_dir: Path) -> None:
    db_path = Path(db_path)
    if not db_path.exists():
        reset_database(db_path)
    from .workflows import WORKFLOWS, initialize_workflow_data, write_import_fixture
    task = os.environ.get("LEDGERDESK_TASK", "monthly-revenue")
    if task in WORKFLOWS:
        initialize_workflow_data(db_path)
        write_import_fixture()
        WorkflowDesk(db_path, Path(export_dir)).mainloop()
    else:
        LedgerDesk(db_path, Path(export_dir)).mainloop()


class WorkflowDesk(LedgerDesk):
    """Ordinary forms for record maintenance in the same native demo app."""
    def __init__(self, db_path: Path, export_dir: Path):
        from .workflows import WORKFLOWS
        tk.Tk.__init__(self)
        self.db_path, self.export_dir = db_path, export_dir
        self.title(WINDOW_TITLE)
        self.geometry("1100x760+35+35")
        self.resizable(False, False)
        self._configure_style()
        self.operation = tk.StringVar(value="Choose an operation…")
        self.status = tk.StringVar(value="Select an operation, enter the requested values, then review.")
        self._result = None
        self._pending = None
        body = ttk.Frame(self, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="LedgerDesk · Operations", font=("DejaVu Sans", 22, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(body, text="DEMO RECORDS ONLY · No external payments or messages").pack(anchor="w", pady=(0, 18))
        selector = ttk.Combobox(body, textvariable=self.operation, values=list(WORKFLOWS.values()), state="readonly", width=55)
        selector.pack(anchor="w", pady=(0, 12))
        selector.bind("<<ComboboxSelected>>", self._select_operation)
        self.form = ttk.LabelFrame(body, text="Record details", padding=12)
        self.form.pack(fill="x")
        self.entries = {}
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=12)
        self.review_button = ttk.Button(controls, text="Review action", command=self._review, state="disabled")
        self.review_button.pack(side="left")
        self.confirm_button = ttk.Button(controls, text="Confirm action", command=self._confirm, state="disabled")
        self.confirm_button.pack(side="left", padx=12)
        self.export_button = ttk.Button(controls, text="Export CSV", command=self._export_workflow, state="disabled")
        self.export_button.pack(side="right")
        self.table = ttk.Treeview(body, show="headings", height=8)
        self.table.pack(fill="both", expand=True, pady=12)
        ttk.Label(body, textvariable=self.status, wraplength=1020).pack(anchor="w")

    def _operation_id(self):
        from .workflows import WORKFLOWS
        return next((k for k, v in WORKFLOWS.items() if v == self.operation.get()), None)

    def _select_operation(self, _event=None):
        from .workflows import FIELDS
        for child in self.form.winfo_children():
            child.destroy()
        self.entries = {}
        self._result = self._pending = None
        self.confirm_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        for index, (name, label) in enumerate(FIELDS[self._operation_id()]):
            row, col = divmod(index, 3)
            ttk.Label(self.form, text=label).grid(row=row * 2, column=col, sticky="w", padx=8)
            entry = ttk.Entry(self.form, width=29)
            entry.grid(row=row * 2 + 1, column=col, sticky="w", padx=8, pady=(4, 10))
            self.entries[name] = entry
        self.review_button.configure(state="normal")
        self.status.set("Enter the requested record details, then click Review action.")

    def _review(self):
        self._pending = (self._operation_id(), {key: entry.get() for key, entry in self.entries.items()})
        self.confirm_button.configure(state="normal")
        self.export_button.configure(state="disabled")
        self.status.set("Review: " + "; ".join(f"{key}={value}" for key, value in self._pending[1].items()) + ". Click Confirm action to apply.")

    def _confirm(self):
        from .workflows import execute_workflow
        if self._pending is None:
            return
        operation, fields = self._pending
        # Editing a field after review invalidates that confirmation.
        if fields != {key: entry.get() for key, entry in self.entries.items()} or operation != self._operation_id():
            self.status.set("Details changed. Review the action again.")
            self.confirm_button.configure(state="disabled")
            return
        self._pending = None
        self.confirm_button.configure(state="disabled")
        try:
            headers, rows = execute_workflow(self.db_path, operation, fields)
        except (ValueError, OSError, sqlite3.Error) as error:
            self.status.set(f"Action failed: {error}")
            with (self.export_dir.parent / "application-audit.jsonl").open("a") as stream:
                stream.write(json.dumps({"operation": operation, "status": "rejected", "fields": fields, "reason": str(error)}) + "\n")
            return
        self._result = operation, headers, rows
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=headers)
        for header in headers:
            self.table.heading(header, text=header.replace("_", " ").title())
            self.table.column(header, width=105, minwidth=60, stretch=True)
        for row in rows:
            self.table.insert("", "end", values=[row[h] for h in headers])
        self.export_button.configure(state="normal")
        self.status.set(f"Action complete. {len(rows)} result rows. Export CSV to save the result.")

    def _export_workflow(self):
        if self._result:
            operation, headers, rows = self._result
            try:
                output = write_csv_export(self.export_dir, operation, headers, rows)
            except OSError as error:
                self.status.set(f"Export failed: {error}")
                return
            self.status.set(f"Export complete: {output.name}.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Open the native LedgerDesk reporting window.")
    parser.add_argument("--db", type=Path, default=Path("output/ledgerdesk.db"))
    parser.add_argument("--export-dir", type=Path, default=Path("output/exports"))
    arguments = parser.parse_args()
    main(arguments.db, arguments.export_dir)
