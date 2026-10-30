# How much does a degree protect in Canada?

An analytics story built by crossing Statistics Canada open datasets, not by charting one table.

**Live app:** deployed on Streamlit Community Cloud from this repo (main file: `app/streamlit_app.py`).

## What it shows

1. **Pressure:** unemployed people per job vacancy, April 2015 to August 2026 (Tables 14-10-0287 and 14-10-0432).
2. **Who feels it first:** unemployment by years living in Canada (Table 14-10-0471).
3. **The cross:** does the gap between recent immigrants and Canadian-born workers close when the market tightens?
4. **Same education, different origin:** unemployment by education level and immigrant group, ages 25 to 54 (Table 14-10-0086).
5. **Where the gap opens:** a heatmap of gaps by education level and time in Canada.

Headline reading (snapshot, September 2026): with a university degree, unemployment is 6.0% among immigrants and 3.5% among Canadian-born workers. The 6.0% is above the 4.4% of a Canadian-born worker with a college or trades diploma. Every figure on the page is computed from the data files, not typed in.

## Method and limits

- Each series is requested one at a time from the StatCan Web Data Service and checked to be the series asked for (coordinate echo).
- Checks before charting: immigrant total sits between its subgroups; total population sits between Canadian-born and immigrants; the education table's total rate matches the official rate over the same period; the April to June 2026 vacancy ratio matches the official Q2 figure.
- Vacancy data has a gap from April to September 2020 in all StatCan vacancy tables checked; the charts show it as a gap, not an interpolation.
- Surveys carry sampling error and Table 14-10-0086 publishes the estimate only. Read patterns, not decimals.
- The analysis does not control for age, region, language or occupation. It shows gaps, not causes.
- The page is a static snapshot (`data/*.json`, embedded in `story/story_en.html`). It does not refresh automatically.

## Repo layout

```
app/streamlit_app.py     Streamlit entry point (embeds the story page)
app/legacy_explorer.py   earlier explorer on synthetic demo data (not deployed)
story/story_en.html      self-contained page (d3 + data inlined)
data/                    JSON snapshot used by the page
published_demo/, src/, tests/, notebooks/   earlier groundwork
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Or just open `story/story_en.html` in a browser.

## Deploy

Streamlit Community Cloud: repo `antonioninocol/stats-canada-b-cases`, branch `main`, main file `app/streamlit_app.py`. It redeploys on every push to `main`.

## Sources

Statistics Canada, tables 14-10-0287, 14-10-0432, 14-10-0471, 14-10-0086, 14-10-0019. Contains information licensed under the Statistics Canada Open Licence.
