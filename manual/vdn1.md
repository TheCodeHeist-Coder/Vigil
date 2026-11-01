<!-- page 1 -->
# VDN-1 Display Node Assembly Manual

Document VDN-1-AM, revision 2. The VDN-1 is a demonstration product built from real parts: an STM32 board driving an OLED display over I2C.

| Revision | Change |
| --- | --- |
| 1 | First release |
| 2 | Added unit Rev B, which arrives with the display already fitted |

Read chapter 4 at the bench. Chapters 3, 5 and 6 hold the wiring, the values and the rules that chapter 4 depends on.

<!-- page 2 -->
## 1 Scope

### 1.1 Purpose

This manual defines how to assemble, inspect and rework the VDN-1 display node at a manual workbench. It applies to every operator and every unit.

### 1.2 Unit revisions

Two unit revisions are in production. Rev A ships as loose parts, and the operator fits the display. Rev B ships with the OLED display already fitted to the breadboard. The revision is printed on the unit traveller.

### 1.3 Order of work

Steps must be done in the published order unless a note in this manual allows otherwise. An operator must not change the order. A step is complete only when its check passes.

<!-- page 3 -->
## 2 Safety and handling

### 2.1 Power off while wiring

Never change a wire while the board has power. All wiring must be complete before the USB cable is connected, because a loose wire on a live board can short 3V3 to GND and damage the STM32 or the display.

### 2.2 Electrostatic protection

Hold the boards by their edges. Do not touch the display glass or the pins of the STM32.

### 2.3 Stop rules

Stop work when the system calls a hold, when a part is damaged, or when a check fails. Do not continue until the fault is corrected or a supervisor releases the unit.

<!-- page 4 -->
## 3 Parts, tools and specifications

### 3.1 Parts list

| Item | Part | Bin | Quantity |
| --- | --- | --- | --- |
| 1 | STM32 board | A | 1 |
| 2 | OLED display, 0.96 inch, I2C, 4 pin | B | 1 |
| 3 | Power wires, red and black | C | 2 |
| 4 | Signal wires, yellow and blue | D | 2 |
| 5 | USB cable | E | 1 |

The breadboard stays in its marked position on the bench and is not a bin item.

### 3.2 Tools

No tools are needed. Use a bright light over the bench, so the wires can be seen clearly.

<!-- page 5 -->
### 3.3 Electrical specifications

| Item | Value |
| --- | --- |
| Display supply | 3V3 from the STM32 board |
| Display controller | SSD1306, 128 by 64 pixels |
| Display I2C address | 0x3C |
| STM32 I2C port | I2C1 |
| Board power | USB, 5V, regulated to 3V3 on the board |

### 3.4 Wiring table

| Wire | Colour | STM32 pin | Display pin |
| --- | --- | --- | --- |
| W1 | Red | 3V3 | VCC |
| W2 | Black | GND | GND |
| W3 | Yellow | PB6 | SCL |
| W4 | Blue | PB7 | SDA |

Display pin order differs between makers, so always read the labels printed on the display. A reversed VCC and GND can destroy the display.

<!-- page 6 -->
## 4 Assembly procedure

Complete the steps in order. Take each part from the bin named in the step.

### 4.1 Seat the STM32 board on the breadboard

Take the STM32 board from bin A. Press it into the breadboard so it spans the centre gap, with all pins fully seated. The board must sit flat.

### 4.2 Seat the OLED display on the breadboard

Take the OLED display from bin B. Press it into the breadboard beside the STM32 board, keeping its four pins in separate rows.

Note 4.2: Rev B units ship with the display already fitted. On a Rev B unit, skip step 4.2 and start at step 4.3. This is not a sequence error.

<!-- page 7 -->
### 4.3 Connect the two power wires

Take the red and black wires from bin C. Connect the red wire from 3V3 to VCC, and the black wire from GND to GND. The display must already be seated on Rev A units, because its pins set where these wires go.

### 4.4 Connect the two signal wires

Take the yellow and blue wires from bin D. Connect the yellow wire from PB6 to SCL, and the blue wire from PB7 to SDA. Four wires must now run between the STM32 board and the display.

### 4.5 Plug in the USB cable last

Take the USB cable from bin E. Plug it into the STM32 board only after all four wires are connected. The USB cable must never be connected before the wiring is finished.

<!-- page 8 -->
## 5 Inspection

### 5.1 In-process checks

Check each step before starting the next one, with hands clear of the breadboard. A step that fails its check must be corrected before work continues.

### 5.2 Final inspection

A finished unit shows the STM32 board and display seated, four wires between them, and the USB cable connected to the board.

### 5.3 Acceptance criteria

Reject a unit if fewer than four wires are connected, if a wire is in the wrong pin, if the display is missing on Rev A, or if the USB cable was connected before the wiring was finished.

<!-- page 9 -->
## 6 Rework

### 6.1 Sequence errors

If a step is done out of order, disconnect the USB cable first if it is connected. Then remove every part fitted after the missed step, complete the missed step, and continue in order.

### 6.2 Wiring errors

If a wire is missing or in the wrong pin, disconnect the USB cable, correct the wire against the wiring table in section 3.4, and inspect the unit again.

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
