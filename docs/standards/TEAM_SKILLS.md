# ProjectMind shared Codex skills

The eight skills in `.agents/skills/` are actual files copied from
[`mattpocock/skills`](https://github.com/mattpocock/skills) at commit
`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`. Their contents and supporting
files are unchanged. The upstream MIT license is in
`.agents/skills/LICENSE.mattpocock`. This commit pins the same skill version for
all four teammates: pull this repository and open it as the Codex workspace.
Use a skill by naming it explicitly in the request, for example `$to-tickets`.

| Skill from the original 12 | Decision | Reason |
| --- | --- | --- |
| `setup-matt-pocock-skills` | Not installed | Existing `AGENTS.md` and SOP are already established; its interactive setup would add another configuration workflow. `docs/agents/issue-tracker.md` supplies the needed tracker setting. |
| `writing-for-agents` | Installed | Helps maintain instructions read by agents. |
| `grill-with-docs` | Not installed | Starts a relentless interview and requires two other skills; the current product review already records open questions. |
| `grilling` | Not installed | Same repeated interview behavior; not needed to start implementation. |
| `domain-modeling` | Not installed | Writes a separate `CONTEXT.md` glossary; ProjectMind's product concepts are still under review. |
| `codebase-design` | Installed | A reference for concrete module and test-interface decisions; `tdd` can consult it. |
| `to-spec` | Installed | Turns an agreed task into a spec and GitHub Issue. Invoke when the product decision is settled. |
| `to-tickets` | Installed | Breaks an agreed spec into demoable, dependent Issues for four-person work. |
| `implement` | Installed | Guides work from a ticket through verification and commit. |
| `tdd` | Installed | Use for behavior with meaningful automated checks, such as Git change analysis. |
| `code-review` | Installed | Checks a committed branch against standards and the originating spec. |
| `handoff` | Installed | Summarizes a session for the next agent; its upstream output is in the OS temporary directory, so put lasting decisions in Issues or repository docs. |

## Team usage

1. Use `to-spec` for a settled task, then `to-tickets` when it needs splitting.
   Both publish GitHub Issues, so inspect their output before invoking them.
2. Implement one Issue on its own branch. Use `tdd` where an agreed behavior can
   be tested. `implement` is optional; ordinary Codex work remains valid.
3. Review a **committed** branch with `code-review`, specifying its base branch
   or commit. Upstream `code-review` compares `<base>...HEAD`; it does not include
   uncommitted changes. If using `implement`, make a checkpoint commit before
   its review step, then commit any review fixes.
4. Use `handoff` for a new session or a new teammate. Keep decisions and task
   progress in shared Issues and docs because the temporary handoff file is
   local to one computer.

`AGENTS.md`, `AGENT_STANDARD.md`, and `TEAM_SOP.md` govern every skill run.
In particular, a skill cannot turn an AI inference into a confirmed Project
Model entry. This skill installation changes team workflow documentation only;
it does not add ProjectMind product functionality.
