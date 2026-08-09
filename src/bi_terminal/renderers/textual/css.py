"""Shared Textual CSS — ported verbatim from bi_python/forms.py's _CSS.

Uses App.CSS (not DEFAULT_CSS) so these rules have higher priority than
widget-level DEFAULT_CSS, matching Textual's documented precedence order.
"""

CSS = """
Screen {
    background: #000080;
    color: #ffffff;
    overflow: auto;
}
ToastRack {
    dock: top;
    align: center top;
    margin-top: 2;
}
ToastHolder {
    align-horizontal: center;
}
Toast {
    background: #000060;
    border-left: outer #55ffff;
}
Toast.-warning {
    border-left: outer #ffff55;
}
Toast.-error {
    border-left: outer #ff5555;
}
#form-title {
    background: #008888;
    color: #000000;
    height: 1;
    padding: 0 1;
    text-style: bold;
}
#form-hint {
    background: #000080;
    color: #5555aa;
    height: 1;
    padding: 0 1;
    border-bottom: solid #005588;
}
#fields {
    padding: 1 1;
    background: #000080;
    height: auto;
}
.row {
    height: 1;
    margin-bottom: 1;
    background: #000080;
    align: left middle;
}
.multirow {
    height: 6;
    margin-bottom: 1;
    background: #000080;
    align: left top;
}
.binrow {
    height: auto;
    margin-bottom: 1;
    background: #000080;
    align: left top;
}
.bin-picker {
    width: 1fr;
    height: auto;
    background: #000080;
}
.lbl {
    width: 18;
    height: 1;
    content-align: right middle;
    color: #55ffff;
    background: #000080;
}
.lbl-top {
    width: 18;
    height: 1;
    content-align: right top;
    color: #55ffff;
    background: #000080;
    padding-top: 0;
}
.lbl-req {
    color: #ffff55;
    text-style: bold;
}
Input {
    width: 1fr;
    height: 1;
    border: none;
    padding: 0 1;
    color: white;
    background: $surface;
}
Input > .input--value {
    color: white;
}
Input > .input--placeholder {
    color: #5555aa;
}
TextArea {
    width: 1fr;
    height: 5;
    border: none;
    padding: 0 1;
    color: white;
    background: $surface;
}
OptionList {
    width: 1fr;
    height: 6;
    border: none;
    background: #000080;
    color: white;
}
OptionList > .option-list--option-highlighted {
    background: #000068;
    color: #ffff55;
}
Switch {
    background: #000080;
    height: 1;
    border: none;
    color: #55ffff;
}
Switch.-on {
    color: #ffff55;
}
Switch:focus {
    border: none;
    background: #000060;
}
.info-row {
    width: 1fr;
    height: 1;
    color: #55ffff;
    background: #000080;
    content-align: left middle;
    padding: 0 1;
}
.info-row:focus {
    color: #ffff55;
    background: #000060;
}
.curr-img {
    width: 1fr;
    height: 1;
    color: #5555aa;
    background: #000080;
    content-align: left middle;
    padding: 0 1;
}
.toggle-hint {
    width: 1fr;
    height: 1;
    color: #5555aa;
    background: #000080;
    content-align: left middle;
    padding: 0 1;
}
#img-note {
    color: #5555aa;
    height: 1;
    width: 1fr;
    content-align: left middle;
    background: #000080;
    padding-left: 1;
}
#img-preview {
    height: 16;
    width: 1fr;
    background: #000030;
    color: #888888;
    overflow: hidden;
    padding: 0 1;
    border-bottom: solid #005588;
}
#img-preview-scroll {
    height: 1fr;
    width: 1fr;
    background: #000030;
}
#img-preview-content {
    width: 1fr;
    height: auto;
    color: #888888;
    padding: 0 1;
}
#footer {
    height: 2;
    background: #000080;
    border-top: solid #005588;
    padding: 0 2;
    align: left middle;
}
DataTable {
    height: 1fr;
    margin: 1 1;
    background: #000050;
    border: none;
}
DataTable > .datatable--cursor {
    background: #000068;
    color: #ffff55;
}
#picker-body {
    padding: 1 1;
    background: #000080;
    height: 1fr;
}
#picker_list {
    height: 1fr;
    margin-top: 1;
}
"""
