# 130 nm CMOS LDO: transistor design and automated verification

A pre-layout, nine-transistor LDO core with a PMOS pass device, PMOS differential input stage, current-mirror load, common-source gate driver, resistor feedback, and compensation. The design was simulated in Spectre using actual 130 nm CMOS transistor models. This public project contains measured numerical exports and executable post-processing.

The operating point is VIN=1.2 V, target VOUT=0.9 V, ideal VREF=0.45 V, and equal 200 kohm feedback resistors. Loads span 100 uA to 5 mA. The principal output capacitor is an **external ideal, zero-ESR 1 nF**. The transistor family has a nominal 1.2 V supply context; sampled terminal voltages are not reliability approval.

See [circuit connections and dimensions](design.md) and [the numerical data](data/). No droop detector or physical reference circuit is claimed in this LDO revision.

## Actual verification coverage

The completed revision comprises **164 static/DC conditions and 10 transient cases**, with 289,248 saved transient samples and 20 measured events. Simulation completion is separate from circuit performance. Recorded warnings remain in the per-case counts; zero-error completion does not mean zero warnings.

| Matrix | Conditions | VOUT range | Core IQ range | Worst native PM / GM |
|---|---:|---:|---:|---:|
| VIN=1.2 V; 5 process corners × 3 temperatures × 3 loads | 45 | 0.899933–0.900087 V | 63.72–77.19 uA | 63.89 deg / 16.22 dB |
| VIN=1.1 V; 5 corners × 3 temperatures × 2 loads | 30 | 0.899800–0.900040 V | 54.69–68.97 uA | 66.23 deg / 19.87 dB |

Temperatures are −40/27/125 C. The 1.2 V matrix uses 0.1/1/5 mA; the 1.1 V matrix uses 0.1/5 mA. These are discrete model samples, not continuous-range closure, mismatch yield, or silicon measurements. At VIN=1.1 V, slow/slow −40 C light load, the tail-device saturation margin is only about 0.44 mV. Successful DC regulation does not establish ample lower-supply headroom.

## Transient results and tradeoffs

Load changes occur at 5 and 30 us, and observation ends at 60 us. Results below use the complete saved samples with explicit event windows. Recovery starts at **ramp end** and uses the last linearly interpolated entry into the fixed 0.891–0.909 V band, remaining in that band only to the event observation end.

| Load case, external Cout=1 nF | Up undershoot | Down overshoot | Up / down recovery | Unload secondary undershoot |
|---|---:|---:|---:|---:|
| Nominal, 100 ns ramp | 126.823 mV | 117.720 mV | 1.690 / 2.318 us | 15.472 mV |
| Nominal, 10 ns ramp | 132.183 mV | 121.145 mV | 1.742 / 2.419 us | 17.295 mV |
| Slow/slow, 125 C, 100 ns ramp | 165.554 mV | 157.242 mV | 1.954 / 3.439 us | **47.707 mV** |

Secondary undershoot is the minimum after the unload event's primary VOUT maximum. The high-temperature result shows why primary peak reduction alone is an incomplete objective. Four corner transients are available; this does not establish transient closure across the whole PVT matrix.

For input steps 1.1→1.2→1.1 V with 100 ns ramps, light-load overshoot/undershoot are 26.104/24.988 mV and heavy-load values are 47.362/43.139 mV. These are time-domain line responses, not a PSRR measurement.

![Actual load and line transient samples](results/figures/transients.png)

## Output-capacitance boundary

| Cout | Load | Native state | Native PM | Native GM |
|---|---:|---|---:|---:|
| 1 nF | 0.1 / 1 / 5 mA | stable at all three points | 72.44 / 76.17 / 74.76 deg | 38.46 / 23.19 / 18.47 dB |
| 100 pF | 0.1 mA | stable | 67.62 deg | 18.55 dB |
| 100 pF | 1 mA | stable, inadequate margin | 15.72 deg | 3.71 dB |
| 100 pF | 5 mA | stable, inadequate margin | 6.62 deg | 1.27 dB |
| 10 pF | 0.1 / 1 / 5 mA | **unstable at all three points** | null | null |

PM≥60 deg and GM≥10 dB were exploratory screening goals. The native unstable classifications and missing margins are preserved. A native stable classification with small margins is not an application-wide success. The principal supported test condition remains 1 nF; a minimum acceptable capacitor between 100 pF and 1 nF has not been established. This revision did not repeat small-C transient failure runs.

## DC, PSRR, noise, and numerical scope

- Nominal load regulation uses the 0.1–5 mA endpoints: −0.01185 mV/mA. Nominal line regulation over VIN=1.1–1.2 V is 0.3753 mV/V at 0.1 mA and 0.4766 mV/V at 5 mA.
- Dropout is a 1% VOUT reduction relative to the same load at VIN=1.2 V. The 10 mV VIN sweep brackets its transition at 0.89–0.90 V for light load and 1.02–1.03 V for heavy load. Interpolation does not justify finer physical precision.
- Core IQ is supply current minus commanded load current, including amplifier, bias, driver, and divider. Ideal-reference power is outside this measurement.
- PSRR is −20log10|VOUT(ac)/VIN(ac)|. Reference supply coupling is idealized. Output RMS noise integrates sampled ASD squared over **10 Hz–100 MHz**; light/heavy values are 166.98/352.99 uV RMS, without physical reference noise.
- Matched maxstep checks use 5 versus 2.5 ns for the 100 ns ramp, and 1 versus 0.5 ns for the 10 ns ramp. Maximum change in a primary VOUT peak is about 11.864 uV. Maximum pointwise VOUT differences between saved interpolants are 56.312/30.503 uV respectively. These finite refinements are numerical sensitivity checks, not asymptotic or physical accuracy guarantees.
- Layout parasitics, capacitor area, ESR sensitivity, mismatch, real reference, startup, and device reliability qualification are outside the reported validation.

![Nominal loop gain, PSRR and noise](results/figures/loop_psrr_noise.png)
![Discrete PVT samples](results/figures/pvt.png)
![Nominal DC input sweep](results/figures/dc_sweep.png)

## Reproduce the public analysis

Python 3.10 or later is sufficient for numerical analysis. Install matplotlib only if figures are desired. From the repository root:

```text
python -B projects/ldo-130nm/scripts/reproduce.py --outdir reproduced/ldo
```

For measurements without plots:

```text
python -B projects/ldo-130nm/scripts/reproduce.py --outdir reproduced/ldo-numeric --no-plots
```

Choose a fresh output directory. The script remeasures all 20 events, checks agreement with the retained exports, recomputes the two full-wave comparisons, retains native scalar stability results, and generates `summary.json`, `events.csv`, `convergence.json`, and optional figures. Only the plots of transients use exported samples; native margins and static PVT scalars are published simulator results, not re-created simulations. CSV inputs use SI units and strictly increasing axes.

The [committed results](results/) were regenerated with this script. The public data can reproduce measurements and plots; rerunning the transistor simulations requires an independently configured, authorized technology environment. Circuit performance and original simulator completion are not independently certified by this post-processing package.
