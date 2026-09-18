import pandas as pd

df = pd.read_csv("pricing_diff.csv")
df["diff"] = df["v2_total"] - df["v1_total"]

# ---------------------------------------------------------------
# Q1: naive count of rows where v2_total != v1_total
# ---------------------------------------------------------------
q1_naive_nonzero_count = int((df["v2_total"] != df["v1_total"]).sum())

# ---------------------------------------------------------------
# Explore where the "big" (non-noise, non-books) differences live
# ---------------------------------------------------------------
nonbooks = df[df["category"] != "books"].copy()
big = nonbooks[nonbooks["diff"].abs() > 0.05]

# every row in `big` turns out to be category == "fragile" AND express == True
assert big["category"].nunique() == 1 and big["category"].iloc[0] == "fragile"
assert big["express"].all()

affected_mask = (df["category"] == "fragile") & (df["express"] == True)

# Sanity: is this mask exactly the set of "big" diffs?
assert set(df[affected_mask].index) == set(big.index)

# ---------------------------------------------------------------
# Q2: exact number of orders with a genuine pricing regression
# ---------------------------------------------------------------
q2_affected_count = int(affected_mask.sum())
q2_affected_category = "fragile"  # combined with express == True

# ---------------------------------------------------------------
# Q3: total dollar amount customers were overcharged
# ---------------------------------------------------------------
q3_total_overcharge = round(float(df.loc[affected_mask, "diff"].sum()), 2)

# ---------------------------------------------------------------
# Q4: baseline mean absolute diff, excluding books and excluding the
# affected (fragile & express) orders -- i.e. pure floating point noise
# ---------------------------------------------------------------
baseline_mask = (df["category"] != "books") & (~affected_mask)
q4_baseline_mean_abs_diff = round(float(df.loc[baseline_mask, "diff"].abs().mean()), 6)

# ---------------------------------------------------------------
# Bonus investigation: what does the extra charge look like?
# Fit diff ~ a * distance_km + b, separately for orders with vs.
# without the SAVE10 coupon, within the affected (fragile+express) group.
# ---------------------------------------------------------------
fe = df[affected_mask].copy()
fe["has_coupon"] = fe["coupon"].notna()

import numpy as np
for has_coupon, g in fe.groupby("has_coupon"):
    X = np.column_stack([g["distance_km"].values, np.ones(len(g))])
    y = g["diff"].values
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    slope, intercept = coef
    pred = X.dot(coef)
    resid = y - pred
    print(f"coupon={has_coupon}: diff ~= {slope:.4f}*distance_km + {intercept:.4f} "
          f"(max residual {np.abs(resid).max():.4f})")

# ---------------------------------------------------------------
# Print everything
# ---------------------------------------------------------------
print()
print("q1_naive_nonzero_count   :", q1_naive_nonzero_count)
print("q2_affected_count        :", q2_affected_count)
print("q2_affected_category     :", q2_affected_category, "(+ express == True)")
print("q3_total_overcharge      :", q3_total_overcharge)
print("q4_baseline_mean_abs_diff:", q4_baseline_mean_abs_diff)
