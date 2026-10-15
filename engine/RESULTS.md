# Matching engine upgrade: results

Run on Zack's inputs (club_info.csv, prof_info.csv, lecture_info.csv; identical to the
copies in the project folder) on 2026-10-15. Reproduce with:

```
python3 -m engine club_info.csv prof_info.csv lecture_info.csv --modes legacy_greedy,best_fit,most_clubs,balanced,top_choices --out OUTPUTS
```

## What was fixed

| Review item | Fix |
|---|---|
| 1. Five professors lost to name typos | Names are matched forgivingly and each fix is listed in `data_issues`. All 41 professors now have lectures. |
| 2. First professor row skipped | Only a real survey label row is dropped. Francisco Aragon is back. |
| 3. weights.json ignored and destructive | Weights are now multipliers (0 = ignore, 2 = double) and are actually applied. Old keys (`size_weight` ...) still load. |
| 4. Titles cut at first hyphen | The split happens at "- <Month>", so "Ever-Changing" and "Twentieth-Century" survive. |
| 5. Curly vs straight apostrophes | Normalised. Akron now gets credit for Chiang's LLM talk. |
| 6. Past speakers unused | Flagged on every match (`repeat_speaker`). Balanced avoids them. |
| 8. Crashes on blank size or score | These fall back to a middle value with a warning. A missing column gives a clear error. |
| (new) Lecture availability ignored | A lecture only counts if it is offered in a month both sides are free. |
| (new) Club ranking ignored | A club's Theme 1 request counts more than its Theme 5 request. |
| (new) Same-month double booking | Each match gets a `suggested_month`. A professor's events are placed in different months where possible. |

## The plans side by side (default weights, with travel wishes)

| | Old greedy | **Recommended** | Best fit | Most clubs | Balanced |
|---|---|---|---|---|---|
| Clubs matched (of 52) | 40 | 40 | 40 | 40 | 40 |
| Got their exact 1st-choice lecture | 23 | 31 | 23 | 21 | 19 |
| Got a lecture they asked for | 38 | 40 | 38 | 39 | 38 |
| Repeat speakers | 1 | 0 | 1 | 1 | 0 |
| Matches that suit the professor's travel wishes | 9 | 7 | 8 | 8 | 12 |
| Matches against a stated travel wish | 2 | 2 | 2 | 2 | 2 |
| Professors used (of 41) | 26 | 27 | 24 | 26 | 31 |
| Same as staff's 2026 Assignment | 26 | 29 | 24 | 23 | 22 |
| Total score | 941 | 893 | 948 | 945 | 936 |

**Recommended** is the default. It ranks its goals strictly, and each one counts for more than everything below it:
1. Serve as many clubs as possible.
2. Give each club the lecture it ranked highest.
3. Avoid repeat speakers.
4. Follow professors' travel wishes.
5. Spread events across faculty and get the best content fit.

The 12 clubs without a speaker sent in no request form. For each of them, the unmatched sheet lists up to three professors who still have open slots. Professors who asked for that club by name come first (for example, David Go asked for Dallas). Staff can make those calls by hand.

Associate titles now get a smaller boost than full ones. "Associate Dean" is ×1.10 instead of ×1.20 for a dean. "Vice President and Associate Provost" counts as vice president (×1.25).

## Professors' travel wishes, as the engine reads them

Each answer to "Particular clubs or areas of the country you are interested in traveling?" is read into places, states, regions and styles (see `engine/geo.py`). Every club is placed by its name using a bundled table (`engine/geo_data.py`). The Region column is not used, because it is often wrong: it lists Utah as "Latin America & the Caribbean". Places they say they've already visited ("I have already done Wichita…") are ignored.

How a club scores for a professor, best match first:

| match | fit |
|---|---|
| a club they named | +1.0 |
| within about 80 km of a city they named | +0.85 |
| in a state they named | +0.7 |
| within the drive limit they gave ("4 hour drive from South Bend") | +0.6 |
| within about 250 km of a place they named | +0.6 |
| in a region they named ("mountain west", "East coast") | +0.5 |
| a major metro for someone who prefers major cities, or a size AA/A club for someone who prefers those | +0.5 |
| a small city for someone who prefers major cities | −0.6 |
| beyond their drive limit | −0.6 |
| smaller than the AA/A clubs they prefer | −0.3 |
| blank answer, "anywhere", or no match | 0 |

Penalties apply only when the professor didn't also say they'd go anywhere. In the score, the fit is worth up to 6 points at weight 1, or −3.6 when a match goes against a wish. Recommended counts it more (up to 40), between "no repeat speakers" and fit.

Clubs placed approximately (please check): Hanover Township (taken as Luzerne County, PA) and Tri-State (taken as the Evansville area).

| professor | their answer | read as |
|---|---|---|
| Francisco Aragon | San Diego, California San Francisco, California | clubs: san diego, san francisco |
| Scott Barton | Hawaii, Puerto Rico, Virgin Islands, Alaska | states: Alaska, Hawaii, Puerto Rico; regions: Virgin Islands |
| John Behrens | Los Angeles Western Montana | clubs: los angeles, western montana |
| Neil Boothby | Fairfield County, CT NYC Washington DC San Diego San Francisco | clubs: fairfield county, san diego, san francisco; near: washington, dc, nyc |
| Nitesh Chawla | San Francisco, Orange County, Phoenix, New York City, | clubs: new york city, orange county, phoenix, san francisco |
| David Chiang | Los Angeles | clubs: los angeles |
| Martijn Cremers | I have a preference for major cities, where I could potentially meet ND benefactors during… | prefers major cities |
| John Deak | I'd love to go to St. Louis. But I also grew in North Carolina and Pennsylvannia, if you h… | clubs: st. louis; states: North Carolina, Pennsylvania; happy to go anywhere |
| Leonard DeLorenzo | I really love going south! And I am from California, so San Diego and Orange County are ho… | clubs: orange county, san diego; states: California; regions: South |
| Bill Evans | I ahve agreed to do a Hesburgh lecture in Pittsburgh in November | clubs: pittsburgh |
| Heather Foucault-Camm | I am profoundly honored to be included among the list of people deemed worthy to contribut… | no preference |
| Richard Garnett | I prefer AA and A sized clubs (or, clubs in the mountain west between January and April). | regions: Mountain West; prefers A/AA clubs |
| David Go | Dallas, TX Richmond, VA Rochester, MN | clubs: dallas, richmond; near: rochester, mn |
| Brad Gregory | (blank) | no preference |
| Michael Hildreth | Latin America? (although, my Spanish isn't that great, this is an area we are trying to ta… | regions: Latin America |
| Beth Hlabse | I'd be interested in visiting clubs where our program has had significant partnerships wit… | clubs: los angeles; near: washington, dc, orange (ca), lexington, hartford, newark |
| Bruce Huber | Seattle, San Francisco, Boston/New England, Utah | clubs: san francisco; near: seattle, boston; states: Utah; regions: New England |
| Fr. Emmanuel Katongole | (blank) | no preference |
| Matt Kloser | San Jose, San Francisco, Bay Area = I went to Stanford for my PhD so know the area well. C… | clubs: chicago, columbus, denver, detroit, fort wayne, greater dupage, lansing, milwaukee, san francisco, san jose/silicon valley; near: indy; states: Michigan |
| Fr. Paul Kollman, CSC | Cincinnati New York City Lexington, KY | clubs: cincinnati, new york city; near: lexington |
| Angela Logan | (blank) | no preference |
| Maria McKenna | I will travel anywhere for our work. I am interested in Los Angeles (and surrounding areas… | clubs: los angeles, st. louis; states: Kentucky; regions: Canada; happy to go anywhere |
| Jessica McManus Warnell | (blank) | no preference |
| Shahriar Mobashery | Washington, DC and San Francisoc, if possible | clubs: san francisco; near: washington, dc |
| Michael Morris | I am open but any of the Florida clubs would be great. I have already done Wichita, Clevel… | states: Florida; happy to go anywhere |
| Bernard Nahlen | California Hawaii Washington DC Arkansas | near: washington, dc; states: Arkansas, California, Hawaii |
| Clive Neal | No - I am willing to go where ever the interest is. | happy to go anywhere |
| Michael O'Malley | I have presented to the clubs in Fort Worth, Wilmington, NC, Honolulu, and San Diego. All … | happy to go anywhere |
| Cara Ocobock | East coast and midwest | regions: East Coast, Midwest |
| Margaret Pfeil | San Diego Northern New Jersey | clubs: northern new jersey, san diego |
| Michael Pippenger | Las Vegas New Mexico Southern Colorado Santa Barbara | clubs: las vegas, santa barbara, southern colorado; states: New Mexico |
| Emilia Justyna Powell | Wyoming Miami Sarasota | clubs: miami; near: sarasota; states: Wyoming |
| Michael Pries | California or Arizona | states: Arizona, California |
| Gabriel Reynolds | California, Hawaii, Arizona, or New York City pls | clubs: new york city; states: Arizona, California, Hawaii |
| Paul Scherz | Charlottesville, VA, Washington, DC, San Francisco or Silicon Valley, CA | clubs: charlottesville, san francisco, san jose/silicon valley; near: silicon valley, washington, dc |
| Jim Schmiedeler | It doesn't really matter | happy to go anywhere |
| Walter Sheirer | I'm open to speaking at any club. Last year I was supposed to do a lecture for the Gettysb… | clubs: gettysburg; happy to go anywhere |
| Chris Stevens | Yes I can do a couple.... I have had to fly a lot to do these... I am happy to do any 4 ho… | within 4h drive of South Bend |
| Jim Sullivan | Any Bay Area club; San Diego; DC; FL; Boston; Philly; Nashville; Dallas/Fort Worth | clubs: dallas, fort worth, nashville, san diego; near: bay area, boston, philly, dc; states: Florida |
| Abraham Winitzer | Open to anything. | happy to go anywhere |
| J.J. Wright | (blank) | no preference |

## Decisions

- 2026-10-15: Zack asked for the best matches that serve as many clubs as possible and make people happiest. That became the Recommended plan, which is now the default. Associate titles were lowered.
- 2026-10-15: Zack asked for travel wishes to count ("you don't want someone who is all big city being sent to Kansas"). They are now a soft preference on every plan, with the `travel_bonus` dial. The Region column is no longer used.
