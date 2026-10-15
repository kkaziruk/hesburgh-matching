# Hesburgh Lecture Matching: staff app

A web page where staff upload the club, professor and lecture spreadsheets (Excel or CSV)
and get several matching plans side by side (Recommended first, then Best fit, Most clubs served and Balanced),
a data check, and Excel downloads.

## Tabs

**Start here** (what to have ready, and how it works), **1 · Upload sheets**, **2 · Adjust priorities**,
**3 · Compare plans** (plans side by side, with the better figure on each line highlighted and a
"Why Recommended?" box), **4 · Dashboard** (charts comparing the plans, plus one plan in detail),
**5 · Download** (choose which plans go in the Excel file).

## Priorities

The **2 · Adjust priorities** tab has quick choices (Standard, Big clubs first, Active clubs first,
Clubs' wishes first, Fresh faces, Share the faculty, Keep our picks) and controls set in plain
levels: Off, Low, Standard, High, Max. They are grouped as *Which clubs come first* (Bigger clubs
first, Most active clubs first), *What makes a good match* (Respect clubs' rankings, Senior
speakers, and, once the engine supports them, Exact talk requested, Easy to schedule, Preferred
talk format, Agree with our team's picks) and *Fairness* (Avoid repeat speakers, Share talks across
faculty, Honour travel wishes). Each has a **What does this do?** link with a plain explanation.
Every plan recalculates as soon as a control moves. The **Save or reuse settings** sub-tab
downloads them as a file and loads them back (an old weights.json also works). Every Excel
download includes a "Settings used" sheet. Priorities and column choices are saved together.

## Spreadsheet columns

The app finds information by column heading, not by position, so you can **add new
columns or reorder them freely**. Small changes to a heading (capitals, spaces,
punctuation, an obvious typo) are recognised automatically.

### Do not rename these columns

Matching can't run without them. If one is renamed, the app stops and asks you to
point it at the right column with a drop-down on the **1 · Upload sheets** tab.

| Sheet | Column heading | What it holds | Also recognised as |
|---|---|---|---|
| club_info | `ID Number` | Unique club ID | Club ID, ID |
| club_info | `Club Check` | Club name | Club, Club Name |
| club_info | `Availability` | Months the club can host, comma-separated | Months, Available Months |
| club_info | `Theme 1` … `Theme 5` | The club's ranked requests ("Theme \| Lecture- months") | Theme 6, Theme 7 … are picked up too |
| prof_info | `Recipient Full Name` | Professor's full name | Full Name, Name, Professor, Faculty |
| prof_info | `Availability` | Months available, or "All of the above" | Months, Available Months |
| lecture_info | `Faculty` | Professor who gives the lecture | Professor, Speaker, Name |
| lecture_info | `Theme` | Theme the lecture belongs to | Category |
| lecture_info | `Topic` | Lecture title, spelled as clubs request it | Title, Lecture, Lecture Title |

### Optional columns (better results when present)

| Sheet | Column heading | Used for |
|---|---|---|
| club_info | `Size` | Club size code AA … F (priority) |
| club_info | `HLS Score` | Engagement score (priority) |
| club_info | `Region` | Shown in results |
| club_info | `Format` | Talk formats the club wants |
| club_info | `Invited 2026` | Which clubs are in this year's program. Next year, `Invited 2027` is picked up automatically. |
| club_info | `2025 Speaker` … `2022 Speaker` | Avoiding repeat speakers. New years are picked up automatically. |
| club_info | `2026 Assignment` | Comparing the plans with staff's own picks |
| prof_info | `# of Events` | Most events a professor will do (blank = 1) |
| prof_info | `Title` | The seniority boost |
| prof_info | `Format(s)` | Talk formats offered |
| prof_info | `Participate in the Hesburgh Lecture program in 2026?` | Answers starting "No" are skipped |
| prof_info | `Particular clubs or areas of the country you are interested in traveling?` | Professors' travel wishes (Balanced plan) |
| lecture_info | `Availability` | Months the lecture is offered (blank = all year) |

### If a column was renamed

The **1 · Upload sheets** tab says what it couldn't find and shows a drop-down for each item. Pick the column that now holds it. All columns can also be reviewed under **2 · Adjust priorities > If a column heading changed**. **Save my settings** keeps these choices, so next year's sheets work after one **Load saved settings**.

## Run it on a computer

One-time setup (needs Python 3.10+):

    pip install -r ui/requirements.txt

Then, from the project folder:

    streamlit run ui/app.py

It opens in the browser at http://localhost:8501. The data never leaves the computer.

## Put it online (Streamlit Community Cloud, free)

1. Put this folder in a GitHub repository (private is fine). Include `engine/` and `ui/`.
   Do **not** commit the CSVs; staff upload them each time.
2. Sign in at https://share.streamlit.io with that GitHub account and choose
   **Create app**, pick the repository, and set the main file to `ui/app.py`.
3. In the app's **Settings > Sharing**, make it private and invite staff by email.
4. Any change pushed to the repository updates the site automatically.

## Files

- `app.py`: the page.
- `backend.py`: connects the page to the matching engine (`../engine`). If the engine
  isn't present, it falls back to the original matching code so the page still works.
- `.streamlit/config.toml`: colours and upload limits.
