<!-- page 1 -->
# ADN-1 Display Node Assembly Manual

Document ADN-1-AM, revision 2. The ADN-1 is a demonstration product built from real parts: an Arduino Uno, or a compatible clone, wired to an OLED display on a breadboard with jumper wires.

| Revision | Change |
| --- | --- |
| 1 | First release, covering unit Rev A and unit Rev B |
| 2 | Limited to the four parts in the parts list |

Read chapter 4 at the bench. Chapters 3, 5 and 6 hold the wiring, the parts and the rules that chapter 4 depends on.

<!-- page 2 -->
## 1 Scope

### 1.1 Purpose

This manual defines how to assemble, inspect and rework the ADN-1 display node at a manual workbench. It applies to every operator and every unit.

### 1.2 Unit revisions

Two unit revisions are in production. Rev A ships as loose parts, and the operator fits the display. Rev B ships with the OLED display already fitted to the breadboard. The revision is printed on the unit traveller.

### 1.3 Order of work

Steps must be done in the published order unless a note in this manual allows otherwise. An operator must not change the order. A step is complete only when its check passes.

<!-- page 3 -->
## 2 Safety and handling

### 2.1 Assembled unpowered

The ADN-1 is assembled with no power connected. Do not connect any power to the Arduino at this bench.

### 2.2 Electrostatic protection

Hold the boards by their edges. Do not touch the display glass or the header pins.

### 2.3 Stop rules

Stop work when the system calls a hold, when a part is damaged, or when a check fails. Do not continue until the fault is corrected or a supervisor releases the unit.

<!-- page 4 -->
## 3 Parts and specifications

### 3.1 Parts list

| Item | Part | Bin | Quantity |
| --- | --- | --- | --- |
| 1 | Arduino Uno or compatible clone | A | 1 |
| 2 | OLED display, 0.96 inch, I2C, 4 pin | B | 1 |
| 3 | Jumper wires | C | 4 |

The breadboard stays in its marked position on the bench and is not a bin item. No tools are needed.

### 3.2 Jumper wires

Any colour of jumper wire can be used. Four wires are needed in total: two for power and two for signals.

<!-- page 5 -->
### 3.3 Display specifications

| Item | Value |
| --- | --- |
| Display supply | 3.3V pin of the Arduino Uno |
| Display controller | SSD1306, 128 by 64 pixels |
| Display I2C address | 0x3C |
| Arduino I2C pins | A4 is SDA, A5 is SCL |

### 3.4 Wiring table

| Wire | Purpose | Arduino pin | Display pin |
| --- | --- | --- | --- |
| W1 | Power | 3.3V | VCC |
| W2 | Power | GND | GND |
| W3 | Signal | A5 | SCL |
| W4 | Signal | A4 | SDA |

Display pin order differs between makers, so always read the labels printed on the display. Each wire runs from the Arduino header to the breadboard row of the matching display pin.

<!-- page 6 -->
## 4 Assembly procedure

Complete the steps in order. Take each part from the bin named in the step.

### 4.1 Place the Arduino Uno beside the breadboard

Take the Arduino Uno from bin A. Place it flat on the bench, next to the breadboard, with its pin labels facing up. The Arduino does not plug into the breadboard.

### 4.2 Seat the OLED display on the breadboard

Take the OLED display from bin B. Press it into the breadboard, keeping its four pins in separate rows.

Note 4.2: Rev B units ship with the display already fitted. On a Rev B unit, skip step 4.2 and start at step 4.3. This is not a sequence error.

<!-- page 7 -->
### 4.3 Connect the two power wires

Take two jumper wires from bin C. Connect one from the 3.3V pin to the VCC row, and one from GND to the GND row. The display must already be seated on Rev A units, because its pins set where these wires go.

### 4.4 Connect the two signal wires

Take two jumper wires from bin C. Connect one from A5 to the SCL row, and one from A4 to the SDA row. Four jumper wires must now run between the Arduino and the breadboard.

<!-- page 8 -->
## 5 Inspection

### 5.1 In-process checks

Check each step before starting the next one, with hands clear of the bench. A step that fails its check must be corrected before work continues.

### 5.2 Final inspection

A finished unit shows the Arduino beside the breadboard, the display seated, and four jumper wires between the Arduino and the breadboard.

### 5.3 Acceptance criteria

Reject a unit if fewer than four wires are connected, if a wire is in the wrong pin, or if the display is missing.

<!-- page 9 -->
## 6 Rework

### 6.1 Sequence errors

If a step is done out of order, remove every part fitted after the missed step, complete the missed step, and continue in order.

### 6.2 Wiring errors

If a wire is missing or in the wrong pin, correct the wire against the wiring table in section 3.4, and inspect the unit again.

### 6.3 Damaged parts

Quarantine any damaged part and record it. Do not reuse a display with cracked glass or bent pins.

### 6.4 Repeat faults

If the same fault occurs three times at one step, stop the line and raise the step with the process engineer. Repeat faults point to the method or the instruction, not the operator.

<!-- page 10 -->
## 7 Records

### 7.1 Unit traveller

Record the unit serial, revision, completed steps, faults and rework for every unit.

### 7.2 Incident records

Each confirmed fault needs an incident record that names the step, the fault, the rework carried out and the manual section that applies.

### 7.3 Retention

Keep records for the life of the product. Evidence images follow the same retention period and show the bench, not the operator's face.
