# Availability for coffee chat

Each file is named by profile key: `anagha_palandye.json`, `gaurav_atavale.json`, `kanishkha_s.json`, `nirbhay_r.json`.

## Format

**Option 1: Recurring weekly slots**

```json
{
  "recurring": [
    { "days": ["mon", "tue", "wed", "thu", "fri"], "start": "18:00", "end": "20:00" },
    { "days": ["sat", "sun"], "start": "10:00", "end": "14:00" }
  ],
  "timezone": "America/New_York"
}
```

- `days`: mon, tue, wed, thu, fri, sat, sun
- `start` / `end`: 24h time "HH:MM". Slots are generated as 1-hour blocks inside these ranges.

**Option 2: Explicit slots (specific datetimes)**

```json
{
  "slots": [
    "2025-02-25T18:00",
    "2025-02-26T19:00"
  ]
}
```

Use ISO format `YYYY-MM-DDTHH:MM`. Each entry is one 1-hour slot.

You can combine both: explicit slots are added to any slots from recurring.
