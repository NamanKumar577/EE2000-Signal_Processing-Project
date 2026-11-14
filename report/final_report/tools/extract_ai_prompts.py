#!/usr/bin/env python3
"""
Build AI_PROMPTS.md: every prompt the team typed into Claude Code for this project,
in time order, taken from the local session logs (~/.claude/projects/<project>/*.jsonl).

Kept: text the user typed, pasted text, and the user's answers to the assistant's
multiple-choice questions.  Dropped: tool output, automatic system notes, slash-command
echoes and the automatic context summaries (they were not typed by a person).
Prompts are copied verbatim; nothing is reworded.

    venv/Scripts/python.exe report/final_report/tools/extract_ai_prompts.py <session_dir> <out.md>
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
DROP_PREFIX = ("<local-command", "<command-name>", "<command-message>", "<task-notification>",
               "This session is being continued from a previous conversation", "[Request interrupted")


def clean(t):
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
    t = re.sub(r"<pasted_content[^>]*>", "\n[pasted text]\n", t)
    t = re.sub(r"</pasted_content[^>]*>", "\n[end of pasted text]\n", t)
    return t.strip()


def prompts(path):
    out, models = [], Counter()
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "assistant":
            m = d.get("message", {}).get("model")
            if m and not m.startswith("<"):
                models[m] += 1
            continue
        if d.get("type") != "user" or d.get("isMeta") or d.get("isCompactSummary"):
            continue
        msg = d.get("message", {})
        if msg.get("role") != "user":
            continue
        c = msg.get("content")
        texts = []
        if isinstance(c, str):
            texts = [("prompt", c)]
        else:
            for x in c or []:
                if not isinstance(x, dict):
                    continue
                if x.get("type") == "text":
                    texts.append(("prompt", x.get("text", "")))
                elif x.get("type") == "tool_result":
                    r = x.get("content")
                    r = r if isinstance(r, str) else " ".join(y.get("text", "") for y in r or [] if isinstance(y, dict))
                    if r.lstrip().startswith(("Your questions have been answered", "User has answered")):
                        texts.append(("answer", r))
        for kind, t in texts:
            t = clean(t)
            if not t or t.startswith(DROP_PREFIX):
                continue
            ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).astimezone(IST)
            if out and out[-1][2] == t:          # the log repeats a prompt after a context summary
                continue
            out.append((ts, kind, t))
    return out, models


def main():
    sdir, dst = Path(sys.argv[1]), Path(sys.argv[2])
    sessions = []
    for f in sorted(sdir.glob("*.jsonl")):
        p, models = prompts(f)
        if p:
            sessions.append((p[0][0], f.stem, p, models))
    sessions.sort()
    total = sum(len(s[2]) for s in sessions)
    L = ["# AI prompts used in the project (EE2000, Team 8)", "",
         "This file lists, word for word, every prompt we typed into the AI coding assistant **Claude Code** "
         "(Anthropic) during the final phase of the project, in time order. It is generated automatically from "
         "the assistant's local session logs by `tools/extract_ai_prompts.py`; nothing was reworded or removed except "
         "automatic system text (tool output, status notes and the assistant's own context summaries) and, where "
         "marked with [rest of this prompt omitted ...], a part of a prompt that was not about the project. "
         "Spelling mistakes are ours and were kept. Times are IST.", "",
         f"Sessions: {len(sessions)}. Prompts and answers: {total}.", "",
         "Prompts used with other AI tools in earlier phases (preliminary and mid-term) are listed in Part B.", ""]
    L += ["## Part A: Claude Code sessions (7 to 14 November 2026)", ""]
    for i, (t0, sid, p, models) in enumerate(sessions, 1):
        mdl = ", ".join(m for m, _ in models.most_common()) or "not recorded"
        L += [f"### Session {i}: {t0:%d %b %Y} to {p[-1][0]:%d %b %Y}", "",
              f"Model(s): {mdl}. Session id: `{sid}`.", ""]
        for j, (ts, kind, t) in enumerate(p, 1):
            head = f"**{i}.{j}** ({ts:%d %b, %H:%M})" + (" - answer to the assistant's question" if kind == "answer" else "")
            body = "\n".join("> " + ln if ln.strip() else ">" for ln in t.splitlines())
            L += [head, "", body, ""]
    root = Path(__file__).resolve().parents[3]
    earlier = [("archive/agent_sessions/ORIGINAL_REQUEST.md",
                "Request given to the Antigravity multi-agent tool on 4 Nov 2026 (Python audit and FPGA specification phase)"),
               ("report/mid_term/antigravity_prompt_mtr8_corrections.md",
                "Prompt document given to Antigravity on 27 Oct 2026 to check and correct the mid-term report (MTR-8)")]
    L += ["## Part B: prompt documents given to other AI tools (earlier phases)", "",
          "These are copied verbatim from the files named in each heading.", ""]
    for k, (rel, what) in enumerate(earlier, 1):
        txt = (root / rel).read_text(encoding="utf-8").strip()
        L += [f"### B.{k}: {what}", "", f"Source file: `{rel}`", "", "````markdown", txt, "````", ""]
    dst.write_text("\n".join(L), encoding="utf-8")
    print(f"{len(sessions)} sessions, {total} prompts -> {dst}")


if __name__ == "__main__":
    main()
