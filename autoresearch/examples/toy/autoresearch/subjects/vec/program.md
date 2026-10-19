# Subject: vec

## Goal

`vec.json` holds six numbers. Move them closer to the target the scorer knows and you do not.
The score is the negative distance, so it rises towards 0.

## How you are measured

- score = −‖v − target‖, so every round should shrink the distance
- the scorer tells you which component is furthest off and by how much
- the gate rejects a `vec.json` that is not six numbers

## Ground rules

- change one component per round
