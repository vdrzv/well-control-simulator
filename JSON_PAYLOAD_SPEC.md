# JSON Payload Specification

This document describes the current JSON contract between the FastAPI backend and the Vue frontend.

## Initial Page Payload

The `/run/{case_id}` HTML page injects the initial frontend state into `window.runPageData`.

```json
{
  "caseId": 1,
  "user": "admin",
  "sessionId": "hex-session-id",
  "caseData": {
    "v_num": 50,
    "well_l": 500,
    "v_delta": 10,
    "vpm": 0.024,
    "dppm": 0.008,
    "m3_per_stroke": 0.008,
    "gaz_v": 1,
    "ro": 1200,
    "pu": 1000000,
    "ro_heavy": 1400,
    "V_real": 12,
    "A": 0.024,
    "iters": 2,
    "Pu_delta": 10000,
    "choke_regulator_1": 2,
    "choke_regulator_2": 3,
    "pump_low": 100000,
    "dt": 1
  },
  "mInit": [[288.0, 0.0, 0.0]],
  "frontendInitData": {
    "choke_speed": 0.5,
    "choke_regulator_1": 2.0,
    "choke_regulator_2": 3.0,
    "casing_p": 1000000,
    "drillpipe_p": 100000,
    "heavy_mud_pos": 0.0,
    "pump_speed_init": 0,
    "choke_position_init": 0,
    "total_strokes": 0,
    "annulus_content": [[288.0, 0.0, 0.0]]
  }
}
```

## Update Request Payload

Used by both transports:

- HTTP: `POST /number/{case_id}`
- WebSocket: `WS /ws/number/{case_id}`

```json
{
  "choke_position": 35.0,
  "pump_speed": 60.0
}
```

Fields:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `choke_position` | number | `0` | Current choke opening percentage from frontend controls, from `0` to `100`. |
| `pump_speed` | number | `0` | Current pump speed from frontend controls. Used to calculate strokes per simulation step. |

## Update Response Payload

Returned by `POST /number/{case_id}` and sent back by `WS /ws/number/{case_id}`.

```json
{
  "frontend_init_data": {
    "choke_speed": 0.5,
    "choke_regulator_1": 2.0,
    "choke_regulator_2": 3.0,
    "casing_p": 997569.4,
    "drillpipe_p": 33,
    "heavy_mud_pos": 0.0,
    "total_strokes": 1.0,
    "annulus_content": [[288.0, 0.0, 0.0]]
  }
}
```

Fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `frontend_init_data.choke_speed` | number | Base choke speed used by frontend control logic. |
| `frontend_init_data.choke_regulator_1` | number | First choke speed multiplier/divider. |
| `frontend_init_data.choke_regulator_2` | number | Second choke speed multiplier/divider. |
| `frontend_init_data.casing_p` | number | Current casing pressure in Pa. |
| `frontend_init_data.drillpipe_p` | number | Current drillpipe pressure in Pa. |
| `frontend_init_data.heavy_mud_pos` | number | Normalized heavy mud position in the drill pipe, from `0` to `1`. |
| `frontend_init_data.total_strokes` | number | Accumulated pump strokes. |
| `frontend_init_data.annulus_content` | array | Current annulus cell content. |

`pump_speed_init` and `choke_position_init` are intentionally omitted from update responses. They are only part of the initial `/run/{case_id}` page payload.

## Annulus Content Shape

`annulus_content` is an array of cells. Each cell is a 3-number tuple:

```json
[light_mud, gas, heavy_mud]
```

Example:

```json
[
  [288.0, 0.0, 0.0],
  [240.0, 1.637248, 0.0],
  [0.0, 9.823488, 0.0]
]
```

The frontend uses each tuple to draw the annulus cell fill ratio.

## WebSocket Message Flow

1. Frontend opens `ws://<host>/ws/number/{case_id}`.
2. Frontend sends the update request payload.
3. Backend validates it as `NumberUpdatePayload`.
4. Backend runs the same logic as `POST /number/{case_id}`.
5. Backend sends the update response payload.
6. Frontend merges `frontend_init_data` into `window.runPageData.frontendInitData`.

If WebSocket is unavailable, the current frontend falls back to `POST /number/{case_id}`.
