# Label Guide — did the authors USE AWS?

Version 1.0 · frozen after first 100 papers are labelled together.

Read the evidence sentence and the paper link. Pick ONE label.
If torn, pick the stricter label and write a note.

## The question
Did the authors of THIS paper actually use Amazon Web Services to do
their work? Not "mention it". Not "it exists". USE it.

## The four labels

| Label | Meaning | Example clue |
|---|---|---|
| **U** | Used AWS for the work | "we ran training on Amazon EC2", "data stored in S3" |
| **D** | Used AWS Open Data | "we used the Sentinel-2 dataset from the AWS Registry of Open Data" |
| **C** | Got AWS credits or support | "supported by AWS credits", "AWS Cloud Credits for Research" |
| **M** | Does not count | see reasons below |

U, D, C each mean real use. M means no.

## M — reasons it does NOT count

Write the reason letter next to M.

| Reason | Meaning |
|---|---|
| **P** | Provider list only: "clouds such as AWS, Azure, GCP" — no actual use |
| **R** | Related work / background: describes AWS, does not use it |
| **S** | Survey or review paper about cloud, no own experiment |
| **K** | Future work: "we plan to use AWS" |
| **F** | False positive: AWS = automatic weather station, American Welding Society, etc. |
| **E** | Example or teaching material, not research use |
| **D** | Documentation / tutorial about AWS |
| **X** | Cannot tell from the text available |

## Hard rules (so two people agree)

1. A mention in a list of options = M/P. Not use.
2. "Future work will use AWS" = M/K. Not use.
3. The paper must show the authors ran something on AWS, stored data
   there, or used AWS open data. A citation to an AWS paper is not use.
4. Credits/support with no described use = C (still counts, separate).
5. If the only text is the title, and the title does not prove use,
   label M/X (cannot tell). Do not guess.
6. "Amazon" alone (the company, the river, the forest) = M/F.

## Secondary signal — record, never mix into AWS counts

Tick these in their own column if present. They are NOT AWS use.

- `generic_cloud`: used some cloud, not named as AWS
- `hpc`: used a supercomputer / HPC cluster
- `compute_limited`: authors say they lacked compute

## What to write per paper

- `label`: U / D / C / M
- `m_reason`: letter if label is M, else blank
- `secondary`: any of generic_cloud / hpc / compute_limited, else blank
- `note`: one short line if you were unsure

## Agreement check

Two people label the same ~100 papers. Where they differ, discuss and
fix the guide. Then freeze the guide and label the rest. Report how
often the two agreed (this is a graded quality number).
