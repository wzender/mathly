## MODIFIED Requirements

### Requirement: Practice tests and simulations on request
A student SHALL be able to request, for any coming test of their class, at any time:
- a simulation with all the test's material, its question count and its time limit;
- a practice test in a mode they choose: balanced, focused (on skills that lost points or are still being learned) or manual (on skills they pick).

An open test of the same kind and mode SHALL resume. A manual test SHALL always be new.

#### Scenario: A simulation two days before the test with nothing practised
- **WHEN** a student who has started no skill asks for a simulation
- **THEN** a timed simulation of the test's length starts, drawn from all the material

#### Scenario: A focused practice test with nothing weak
- **WHEN** no skill lost points and none is being learned
- **THEN** the focused mode is offered as unavailable, and asking for it is refused with a message

### Requirement: Readiness from tests only
The readiness number SHALL change only when a practice test or a simulation is handed in. For each one, oldest first, when its grade is above the number, the number SHALL become `number + GAIN × (grade − number)`, with GAIN 0.6 for a simulation, 0.3 for a practice test and 0.15 for a manual one. Mastery of skills SHALL NOT change it.

#### Scenario: A simulation counts more
- **WHEN** a student with readiness 0 hands in a simulation with 80
- **THEN** the readiness is 48, where a practice test with 80 would make it 24

#### Scenario: A bad grade never lowers it
- **WHEN** a student with readiness 76 hands in a practice test with 30
- **THEN** the readiness stays 76
