# Search for an existing bug report

As of November 13, 2026. **No clearly identical existing report was found.** Related issues exist; bug 166485 is the closest candidate and should be mentioned as a possible connection when reporting this case. A common root cause has not been established.

## Reports reviewed

| Report | Current status | Comparison with this reproduction |
|---|---|---|
| [166485 – Memory usage increases with > 2 GB after accepting/rejecting all changes](https://bugs.documentfoundation.org/show_bug.cgi?id=166485) | NEW | Closest general symptom: increased memory usage when accepting or rejecting changes, including table changes. According to comment 4, disabling undo recording prevents the memory increase in that report. It does not establish the same hidden deletion in a single cell or a LOK layout hang; whether these are the same bug remains unresolved. |
| [147464 – Undo rejecting changes freezes LibreOffice](https://bugs.documentfoundation.org/show_bug.cgi?id=147464) | NEW | Hangs after rejecting all changes and then undoing that operation, spending substantial time in `SwRangeRedline::GetExtraData`. Our case hangs while accepting all changes through LibreOfficeKit, without undo. |
| [172195 – Accept All doesn't accept stacked changes](https://bugs.documentfoundation.org/show_bug.cgi?id=172195) | NEW | Incorrect results with overlapping formatting and deletion changes; no documented hang. The example text is not inside a table. |
| [168431 – LibreOfficeKit documentLoad() leads to hang](https://bugs.documentfoundation.org/show_bug.cgi?id=168431) | VERIFIED / FIXED | A Windows/COM regression that hangs while loading ordinary ODT files. Our Linux/LibreOfficeKit case loads successfully and then hangs while accepting changes. |
| [123380 – LibreOfficeKit: Does not load and convert the attached document](https://bugs.documentfoundation.org/show_bug.cgi?id=123380) | NEW | Extremely slow import of an old DOC file containing macros; affects loading. Its reproduction does not match this case. |
| [104814 – Change tracking: accepting changes gets stuck](https://bugs.documentfoundation.org/show_bug.cgi?id=104814) | RESOLVED / FIXED | An old LibreOffice 5.2/5.4 issue involving a change that could not be accepted, fixed in 2016/2017. It does not establish the same root cause in the current case. |

Relevant tracking issues for classifying a new report:

- [138327 – sw_redlinehide regressions](https://bugs.documentfoundation.org/show_bug.cgi?id=138327)
- [143002 – Tracked Changes of tables](https://bugs.documentfoundation.org/show_bug.cgi?id=143002)
- [168467 – LibreOfficeKit issues](https://bugs.documentfoundation.org/show_bug.cgi?id=168467)

## Search method and limitations

The public LibreOffice Bugzilla REST API was searched for titles containing `accept`, `tracked`, `redline`, and `LibreOfficeKit`, including resolved reports. Full-text searches also covered the stack trace signatures `LOKRedlineNotification`, `AcceptAllRedline`, and `SwRootFrame::CalcFrameRects`. The first two returned no matches; the third returned five reports with no matching reproduction description. The descriptions and comments of the candidates listed above were reviewed.

The public GitHub issue search was also queried for “tracked changes” and “LOKRedlineNotification” in `gotenberg/gotenberg`, and for “AcceptAllTrackedChanges” in `gotenberg/lok`. None of these three queries returned a match. The raw responses are stored in the original investigation project under `upstream/gotenberg-issue-search-26.8.3.json`.

A web search for the exact signature did not produce useful Bugzilla results, so this assessment primarily relies on public Bugzilla data read directly. The raw responses are stored in the original investigation project under `upstream/bug-search-*.json` and `upstream/bug-*-comments.json`.

This does not guarantee that no differently worded or unclassified report exists. **Bug 166485 is potentially related, but is not a confirmed duplicate.** The small synthetic fixture and the clear distinction between successful loading and a hang when accepting changes through LibreOfficeKit should help LibreOffice developers classify the issue. The same accept-all operation has not been tested through an external UNO client or the Writer graphical interface, so exclusivity to LibreOfficeKit is not established.

No bug report has been created and no existing report has been commented on.
