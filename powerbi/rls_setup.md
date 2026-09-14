# Row-level security

A dealer sees its own numbers and nobody else's. A regional manager sees their
region. Head office sees everything.

That is three requirements, and getting them from one mechanism is the whole
design problem — the common mistake is three roles with three hand-maintained
member lists, which drifts the moment somebody changes job.

---

## The approach: dynamic RLS driven by a mapping table

Static RLS — a role per dealer, with users assigned to roles in the Power BI
service — needs 40 roles and a membership change every time somebody moves. It
is unmanageable by the second month.

Dynamic RLS puts the mapping in a table the warehouse owns, and one role reads
it. Adding a dealer, moving a manager or granting somebody a second region is a
row change, applied at the next refresh, with no Power BI administration at all.

The cost is real and worth stating: the mapping table becomes a security control
surface. Whoever can write to `gold.security_user_dealer` can grant themselves
any dealer's data. It needs the same change control as the permissions it
replaces — which is why it is loaded from a source rather than edited by hand.

---

## 1. The mapping table

```sql
CREATE TABLE gold.security_user_dealer
(
    user_principal_name VARCHAR(200)    NOT NULL,   -- exactly as Entra ID reports it
    dealer_code         VARCHAR(20)     NOT NULL,   -- '*' means every dealer
    access_scope        VARCHAR(20)     NOT NULL,   -- DEALER | REGION | ALL
    region              VARCHAR(30)     NULL,       -- populated when scope is REGION
    granted_by          VARCHAR(200)    NULL,
    granted_ts          DATETIME2(3)    NOT NULL,
    is_active           BIT             NOT NULL
);
GO
```

`user_principal_name` has to match `USERPRINCIPALNAME()` exactly, and that is
the single most common reason RLS silently shows nothing. In Power BI it returns
the Entra ID UPN, which is not always the address people type — a user signing
in as `burak@mihenk.com.tr` may have a UPN of
`burak@mihenk.onmicrosoft.com`. Confirm it before assuming the filter is wrong:

```dax
Debug UPN = USERPRINCIPALNAME()
```

Put that measure on a card, view the report as the user, and read what it says.
Every hour lost to RLS starts here.

### Seeding it

```sql
INSERT INTO gold.security_user_dealer
(user_principal_name, dealer_code, access_scope, region, granted_by, granted_ts, is_active)
SELECT * FROM (VALUES
    -- Head office: every dealer, every region
    ('genelmudur@mihenk.com.tr', '*',      'ALL',    NULL,        'setup', SYSDATETIME(), 1),
    ('bi@mihenk.com.tr',         '*',      'ALL',    NULL,        'setup', SYSDATETIME(), 1),

    -- A regional manager: every dealer in one region
    ('marmara.bm@mihenk.com.tr', '*',      'REGION', 'Marmara',   'setup', SYSDATETIME(), 1),
    ('ege.bm@mihenk.com.tr',     '*',      'REGION', 'Ege',       'setup', SYSDATETIME(), 1),

    -- A dealer principal: one dealer
    ('byi001@mihenk.com.tr',     'BYI001', 'DEALER', NULL,        'setup', SYSDATETIME(), 1),
    ('byi002@mihenk.com.tr',     'BYI002', 'DEALER', NULL,        'setup', SYSDATETIME(), 1),

    -- Somebody who runs two sites. Two rows, not a special case.
    ('byi015@mihenk.com.tr',     'BYI015', 'DEALER', NULL,        'setup', SYSDATETIME(), 1),
    ('byi015@mihenk.com.tr',     'BYI016', 'DEALER', NULL,        'setup', SYSDATETIME(), 1)
) AS v (user_principal_name, dealer_code, access_scope, region, granted_by, granted_ts, is_active);
GO
```

Multiple dealers is two rows rather than a comma-separated column. A delimited
list would need parsing in DAX, and a list that has to be parsed is a list that
will one day contain a space after the comma.

---

## 2. The role

One role, `DealerAccess`, with the filter on `Dealer`.

**Model → Manage roles → Create**, table `Dealer`, expression:

```dax
VAR CurrentUser = USERPRINCIPALNAME()
VAR HasFullAccess =
    NOT ISEMPTY (
        FILTER (
            ALL ( 'Security User Dealer' ),
            'Security User Dealer'[user_principal_name] = CurrentUser
                && 'Security User Dealer'[access_scope] = "ALL"
                && 'Security User Dealer'[is_active] = TRUE ()
        )
    )
VAR AllowedRegions =
    SELECTCOLUMNS (
        FILTER (
            ALL ( 'Security User Dealer' ),
            'Security User Dealer'[user_principal_name] = CurrentUser
                && 'Security User Dealer'[access_scope] = "REGION"
                && 'Security User Dealer'[is_active] = TRUE ()
        ),
        "r", 'Security User Dealer'[region]
    )
VAR AllowedDealers =
    SELECTCOLUMNS (
        FILTER (
            ALL ( 'Security User Dealer' ),
            'Security User Dealer'[user_principal_name] = CurrentUser
                && 'Security User Dealer'[access_scope] = "DEALER"
                && 'Security User Dealer'[is_active] = TRUE ()
        ),
        "d", 'Security User Dealer'[dealer_code]
    )
RETURN
    HasFullAccess
        || 'Dealer'[region] IN AllowedRegions
        || 'Dealer'[dealer_code] IN AllowedDealers
```

`ALL('Security User Dealer')` on every lookup is not optional. Without it the
mapping table is itself filtered by the role being evaluated, and the expression
becomes circular — which manifests as a user seeing nothing, with no error.

The three scopes are evaluated as an OR, so a user can hold several kinds of
grant at once and gets the union. Somebody promoted from dealer principal to
regional manager keeps working while their old row is still there.

---

## 3. How the filter reaches the facts

RLS is applied to `Dealer` only. It propagates to everything else through the
relationships, which is why the model's relationship directions matter for
security and not only for correctness.

```
Security User Dealer
        │ (no relationship - read with ALL() inside the role expression)
        ▼
     Dealer ──────► Vehicle Sale
        │      ──► Repair Order
        │      ──► Repair Order Line
        │      ──► Vehicle Inventory
        │      ──► Service Summary
        │      ──► Dealer Target
        │      ──► Recall Coverage
        ▼
   (single direction, one-to-many, Dealer on the one side)
```

Two consequences that are easy to miss:

**`Part Purchase` has no dealer.** Purchase orders are placed centrally, so the
procurement page is not filtered by this role at all. That is correct — a dealer
should not see the distributor's supplier pricing — but it means the procurement
page must be excluded from dealer-facing reports rather than relying on RLS to
empty it. **RLS that returns everything is not RLS.**

**`Customer` and `Vehicle` are shared across dealers.** A customer who bought
from one dealer and services at another appears in both. Filtering through
`Dealer` means each dealer sees that customer's rows *for their own
transactions*, which is right. But `DISTINCTCOUNT` of customers will not sum to
the head office total across dealers, and somebody will report that as a bug. It
is not: the same customer is legitimately counted by two dealers.

---

## 4. Bidirectional filters and RLS

**Do not turn on bidirectional cross-filtering between `Dealer` and any fact.**

It is tempting — it makes a dealer slicer hide dealers with no rows in the
current period — and it breaks RLS. With bidirectional filtering, the fact table
can filter the dimension, and a carefully built visual can infer the existence
of rows the user is not allowed to see.

Where a "hide empty dealers" behaviour is genuinely wanted, use a measure-based
visual filter rather than a bidirectional relationship:

```dax
Dealer Has Activity =
IF ( [Sale Count] + [Repair Order Count] > 0, 1, 0 )
```

and filter the visual to `Dealer Has Activity = 1`.

---

## 5. Direct Lake and RLS

RLS defined in the semantic model applies to Direct Lake exactly as it does to
import mode. Two things to know:

**The Warehouse's own security is separate.** A user querying `mihenk_wh`
directly through the SQL endpoint is governed by Warehouse permissions, not by
this role. If dealers are ever given SQL access, the same rules have to be
implemented again there — Warehouse-level RLS on `gold.dim_dealer` is the
equivalent. Do not assume the semantic model's role protects the tables
underneath it.

**Fallback to DirectQuery does not disable RLS**, but it does change the
performance profile enough that a slow report may be the first sign fallback is
happening. Monitor it rather than discovering it.

---

## 6. Testing — and it needs testing

RLS failures are silent in both directions: showing too little looks like no
data, and showing too much looks like it is working.

**In Power BI Desktop:** Model → Manage roles → **View as** → check
`DealerAccess` and enter a UPN.

Test all five of these, and the last two are the ones people skip:

| # | View as | Expect |
|---|---|---|
| 1 | `byi001@mihenk.com.tr` | one dealer, and `Sale Count` matching that dealer's own total |
| 2 | `byi015@mihenk.com.tr` | exactly two dealers |
| 3 | `marmara.bm@mihenk.com.tr` | every Marmara dealer, no others |
| 4 | `genelmudur@mihenk.com.tr` | everything, totals equal to no role at all |
| 5 | `nobody@mihenk.com.tr` | **nothing** — an unmapped user must see zero rows, not everything |

Test 5 is the one that matters. A role expression with a subtle logic error
often defaults to permitting everything, and it looks exactly like a working
report.

Also check the **totals**, not just the visuals. A visual can filter correctly
while a card measure using `ALL()` or `REMOVEFILTERS()` bypasses the role
entirely. Any measure in `measures_dax.md` using `REMOVEFILTERS` — `Warranty
Cost Ratio` and `Service Retention Rate` both do — needs checking under a
restricted role specifically:

```dax
-- Safe: removes the Repair Order filter, leaves Dealer's RLS filter in place
CALCULATE ( [Net Sale Amount], REMOVEFILTERS ( 'Repair Order' ) )

-- NOT safe: would remove the RLS filter too
CALCULATE ( [Net Sale Amount], REMOVEFILTERS ( 'Dealer' ) )
```

`REMOVEFILTERS` on the table RLS is applied to bypasses RLS. Neither measure in
this model does that, and any new one must not either.

---

## 7. Workspace roles

RLS applies to users with **Viewer** access. It is ignored for Admin, Member and
Contributor — those roles can edit the model, so restricting what they can read
would be theatre.

| Workspace role | Who | RLS applies |
|---|---|---|
| Admin | platform owner | no |
| Member | data engineering | no |
| Contributor | report developers | no |
| **Viewer** | dealers, regional managers, head office readers | **yes** |

Which means: **every business user must be a Viewer.** Granting a dealer
principal Contributor access to save an administrative round trip silently
removes their row-level security, and nothing in the interface says so.
