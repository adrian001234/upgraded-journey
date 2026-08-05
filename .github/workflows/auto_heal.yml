name: TechPulse Auto-Heal
on:
  workflow_run:
    workflows: ["TechPulse Pipeline"]
    types:
      - completed
jobs:
  heal:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Attempt auto-heal (opens a PR, never commits to main)
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          FAILED_RUN_ID: ${{ github.event.workflow_run.id }}
        run: python autoheal/heal.py
