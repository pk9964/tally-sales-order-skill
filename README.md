# Tally Sales Order skill

An Agent Skill that teaches AI agents (Claude and other skill-compatible agents) to create, look up and verify **Sales Order vouchers in TallyPrime** through Tally's XML/HTTP interface.

It covers the full loop: resolve masters, avoid duplicates by reference, build the import envelope, read Tally's response, then read the voucher back and check every line. It also records the quirks that break real integrations, such as padded quantities, alternate units, ledger aliases and control characters in Tally replies.

## What's inside

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Instructions the agent follows |
| `scripts/build_sales_order.py` | Builds the import XML from a JSON order and checks the totals (Python 3, no dependencies) |
| `examples/order.json` | Sample order input |
| `references/` | Import template and lookup requests for Sales Orders and masters |

## Install

- **Claude Code:** copy this folder to `~/.claude/skills/tally-sales-order/`.
- **Claude apps:** upload the folder as a skill in Settings.
- **Other agents:** point your agent's skills directory at this folder.

Then ask your agent something like "create a Sales Order in Tally for this order" and it will follow the skill.

## Try the script

```bash
python3 scripts/build_sales_order.py examples/order.json > so.xml
curl -s -X POST --data-binary @so.xml http://localhost:9000
```

TallyPrime must be running with its HTTP server on (default port 9000) and the company open. Test on a copy of your company data first.

## About

Built by [BizMagnets](https://bizmagnets.ai) from production experience running the **AI Agent for Tally**, which lets distributors' customers order on WhatsApp and creates the Sales Order in Tally automatically.

## License

MIT
