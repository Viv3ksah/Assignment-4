# Pricing Refactor Regression — Answers

## Q1. Naive count of `v2_total != v1_total`

**16,000 rows** out of 20,000 have `v2_total != v1_total`.

This is not a useful answer to "how many orders are actually affected by a real
bug" because the vast majority of those 16,000 rows are explained by two things
we already know are *not* bugs: (a) the ~3,335 `books` orders, which changed
because of the intentional per-kg rate change, and (b) harmless floating-point
noise of a cent or two that shows up on almost every order regardless of
category. A raw not-equal count lumps expected, approved changes in with real
problems, so it wildly overstates the scope of the actual regression.

## Q2. Orders affected by a genuine pricing regression

**985 orders** are affected by a genuine bug.

Every single one of these orders shares exactly two input conditions:
- `category == "fragile"`
- `express == True`

There is no genuine-bug diff outside this combination (books diffs are the
documented rate change; every other category/express combination has
diffs no larger than 2 cents, consistent with rounding noise), and *every*
fragile+express order is affected (985 out of 985 such orders), with a
minimum overcharge of $5.08 — far beyond rounding noise.

## Q3. Total dollar amount customers were overcharged

**$19,779.14** total overcharge (v2_total higher than v1_total) across the
985 affected orders. Every affected order was overcharged — none were
undercharged (`diff` for this group ranges from $5.08 to $34.98).

## Q4. Baseline diff for unaffected, non-books orders

For the 15,680 orders that are neither in the `books` category nor part of
the fragile+express affected group, the average absolute difference between
`v1_total` and `v2_total` is:

**$0.00988** (about **1 cent**)

This confirms the affected group is a real, distinct pattern rather than
"everything is a little different": the baseline noise floor is under a
penny on average, while every one of the 985 fragile+express orders was
overcharged by at least $5.08 — three orders of magnitude larger than the
noise floor, and clustered on one exact combination of inputs rather than
scattered randomly across categories.

## Q5 (Bonus). What is the actual code-level bug?

Within the fragile+express group, the overcharge amount is almost perfectly
linear in `distance_km`, and splits cleanly into two lines depending on
whether the `SAVE10` coupon was applied:

- No coupon: `overcharge ≈ 0.10 * distance_km + 5.00`
- With `SAVE10` (10% off): `overcharge ≈ 0.09 * distance_km + 4.50`
  (exactly 90% of the no-coupon line)

That "$5 flat + $0.10/km, discounted along with everything else when a
coupon is applied" shape looks exactly like the standard **express delivery
surcharge**. My read: the refactor likely turned what used to be a single
mutually-exclusive branch (e.g. "if fragile, apply fragile handling fee;
else if express, apply express surcharge") into two independent `if`
statements (a separate fragile-handling check and a separate express check)
that are no longer mutually exclusive. For orders that are *both* fragile
and express, the express surcharge now gets applied a second time — once in
whichever branch used to be "shared" and once again in the express branch —
double-charging exactly the express fee for that one combination of inputs,
while every other category/express combination is unaffected.

---

## Investigation process (dead ends included)

- Started by just comparing `v1_total` vs `v2_total` directly (Q1's naive
  approach) — 16,000/20,000 rows differ, which is obviously too high to be
  "real bugs" given the assignment says only two things are supposed to
  differ, so I knew this number couldn't be the real answer.
- Split by category first, since we were told books had an intentional rate
  change. Books diffs were tightly clustered ($0–$5, all positive, mean
  ~$2.48) which matched a rate-change story, so I set books aside as
  "explained."
- Looked at diff stats for everything else (`category != books`): mean was
  ~$1.19 but with a huge standard deviation (~$5.18) compared to a tiny
  median (~$0.01) — that gap between mean and median was the tell that a
  small subset of rows was dragging the mean up, hiding inside a
  mostly-noise population.
- Filtered non-books rows to `abs(diff) > $0.05` (i.e., clearly more than
  rounding noise) — got exactly 985 rows, and checking `.unique()` /
  `.value_counts()` on category and express for that subset showed they
  were **100% `category == "fragile"` and `express == True`**, no
  exceptions.
- Dead end: initially guessed the bug might correlate with `weight_kg`
  (since fragile items are often weight-sensitive) — checked correlation
  and it was near zero (r ≈ 0.018). Distance, on the other hand, correlated
  almost perfectly with diff (r ≈ 0.995), which redirected the
  investigation toward distance-based fees rather than weight-based ones.
- Confirmed completeness in both directions: every fragile+express order
  (985/985) has a large diff, and no other category/express combination has
  diffs above the ~2-cent noise floor — so the affected set is exactly (and
  only) "fragile AND express," not a fuzzy correlation.
- For the bonus, fit `diff` as a linear function of `distance_km` for the
  affected group. The fit wasn't clean until I noticed some of the residual
  spread lined up with whether `coupon == SAVE10`; splitting the group by
  coupon presence before fitting gave two near-perfect lines (max residual
  ~2-3 cents, i.e. down at the noise floor), and the "with coupon" line was
  exactly 90% of the "without coupon" line — strongly suggesting the
  discount is being applied correctly to a fee that itself shouldn't exist
  a second time. That $5 flat + $0.10/km shape reads as a duplicated
  express surcharge, which led to the double-branch hypothesis in Q5.
