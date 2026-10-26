# How is "Material Circularity Indicator" (MCI) indicator computed in the context of circularity in the built environment?

The Material Circularity Indicator (MCI) is computed by combining a material’s virgin inputs and unrecoverable waste with an adjustment for how long and intensively the product is used. In the built environment, it is generally calculated for individual construction materials or components, then aggregated into a building-level score, commonly using mass weighting. It measures material-flow **circularity**, not environmental impact directly.[^1_1][^1_2]

The core equation is:

$$
\boxed{\mathrm{MCI}=\max\left[0,\;1-\mathrm{LFI}\frac{0.9}{X}\right]}
$$

where $\mathrm{LFI}$ is the Linear Flow Index and $X$ is utility relative to an industry-average equivalent product. The score ranges from 0 to 1, but there is an important convention: a completely linear product with average utility scores 0.1, not zero.[^1_2][^1_3]

## 1. Calculate the material flows

The following equations describe the technical-material case—for example, steel, aluminium, concrete constituents or non-biological insulation—with recycling losses included. Biological materials require additional provisions, discussed below.[^1_4][^1_1]

### Input data

For each assessed material or component, define:


| Symbol | Meaning | Construction interpretation |
| :-- | :-- | :-- |
| $M$ | Product mass | Mass of the assessed component or material |
| $F_R$ | Fraction of input mass from recycled sources | Recycled material incorporated into the product |
| $F_U$ | Fraction of input mass from reused sources | Reused components incorporated into the assessed product |
| $C_R$ | Fraction collected for recycling after use | Share expected to enter a recycling process after deconstruction |
| $C_U$ | Fraction going to component reuse after use | Share expected to be reused rather than processed into material |
| $E_F$ | Efficiency of recycling used to produce the recycled feedstock | Yield of the upstream recycling process |
| $E_C$ | Efficiency of recycling after the product’s use | Yield of the downstream recycling process |

All fractions and efficiencies are expressed from 0 to 1; the input fractions and end-of-use fractions must not double-count the same mass. These variables follow the MCI material-flow methodology.[^1_4]

### Virgin input

$$
V=M(1-F_R-F_U)
$$

Here, $V$ is the virgin material mass entering the product. Increasing recycled content or incorporating reused components reduces it.[^1_4]

### Unrecoverable waste

First calculate material that does not enter reuse or recycling:

$$
W_0=M(1-C_R-C_U)
$$

Then calculate the losses in the two recycling processes:

$$
W_F=M F_R\frac{1-E_F}{E_F}
$$

$$
W_C=M C_R(1-E_C)
$$

The total waste attributed to the product is:

$$
W=W_0+\frac{W_F+W_C}{2}
$$

The half-weighting allocates recycling-process losses between adjacent product cycles, rather than attributing all of them to both products. If there is no recycled feedstock, $W_F=0$; otherwise its calculation requires a positive $E_F$.[^1_5][^1_4]

### Linear Flow Index

$$
\boxed{
\mathrm{LFI}=
\frac{V+W}
{2M+\frac{W_F-W_C}{2}}
}
$$

The numerator represents linear flows: virgin input plus attributed unrecoverable waste. The denominator represents total material flow, corrected for recycling losses. A higher LFI means greater linearity.[^1_5][^1_4]

If both recycling processes are assumed to be perfectly efficient, $E_F=E_C=1$, then $W_F=W_C=0$, and the expression simplifies to:

$$
\mathrm{LFI}=\frac{V+W_0}{2M}
=\frac{(1-F_R-F_U)+(1-C_R-C_U)}{2}
$$

Thus, under this simplifying assumption, LFI is the average of the virgin-input fraction and the unrecovered end-of-use fraction.[^1_2][^1_4]

## 2. Adjust for service life and intensity of use

MCI includes a utility term:

$$
X=\frac{L}{L_{\mathrm{av}}}\frac{U}{U_{\mathrm{av}}}
$$

where:

- $L/L_{\mathrm{av}}$ compares the product’s service life with that of an industry-average equivalent.
- $U/U_{\mathrm{av}}$ compares its intensity of use or functional output with the corresponding benchmark.[^1_2]

For a building component, a lifetime-only calculation takes:

$$
X=\frac{L}{L_{\mathrm{av}}}
\qquad\text{with}\qquad
\frac{U}{U_{\mathrm{av}}}=1
$$

The utility adjustment is then:

$$
F(X)=\frac{0.9}{X}
$$

A longer-lived component therefore receives a higher MCI for otherwise identical material flows. The benchmark matters: a 60-year service life is advantageous relative to a 30-year equivalent, but not relative to a 60-year equivalent. Avoid counting the same benefit twice through both lifetime and cumulative lifetime output. The methodology notes that lifetime or functional units are commonly used exclusively.[^1_2]

The resulting score has the following interpretation:


| Situation | MCI |
| :-- | --: |
| Fully restorative flows, $\mathrm{LFI}=0$ | 1 |
| Fully linear flows, $\mathrm{LFI}=1$, average utility $X=1$ | 0.1 |
| Fully linear flows, twice-average utility $X=2$ | 0.55 |
| Raw calculation below zero | Set to 0 |

These results follow directly from the MCI equation. Consequently, MCI is not simply the percentage of material recycled: longevity can improve it even without material recovery.[^1_3][^1_2]

## 3. Worked construction-component example

Consider a hypothetical 1,000 kg component, with:

- 40% recycled input and 10% reused input;
- 70% collected for recycling and 20% going to reuse after use;
- 100% recycling efficiency at both ends, as a simplifying assumption;
- a 60-year service life compared with a 50-year benchmark;
- the same intensity of use as the benchmark.

Using the equations above:[^1_4][^1_2]

$$
V=1{,}000(1-0.40-0.10)=500\ \mathrm{kg}
$$

$$
W_0=1{,}000(1-0.70-0.20)=100\ \mathrm{kg}
$$

$$
\mathrm{LFI}=\frac{500+100}{2(1{,}000)}=0.30
$$

$$
X=\frac{60}{50}=1.20
$$

$$
\mathrm{MCI}=1-0.30\frac{0.9}{1.20}=0.775
$$

The component therefore scores 0.775, or 77.5 on a 0–100 scale. With the same material flows but average lifetime, $X=1$, it would score 0.73. This example illustrates the separate contributions of material recovery and service life; the inputs are illustrative, not measured construction data.

## 4. Aggregate components into a building score

A mass-weighted building-level implementation uses:

$$
\boxed{
\mathrm{MCI}_{\mathrm{building}}
=
\frac{\sum_i M_i\,\mathrm{MCI}_i}
{\sum_i M_i}
}
$$

where $M_i$ is the assessed mass of material or component $i$. This is explicitly the project-level approach used in eTool. Madaster likewise uses product masses to weight its building score, although its “Madaster Circularity Indicator” is an adaptation of the original Material Circularity Indicator.[^1_6][^1_2]

This aggregation has two practical implications:

- Heavy materials exert more influence than lightweight materials, irrespective of their economic value or environmental impact.
- Component-level and building-layer scores remain useful alongside the overall result, because an aggregate can conceal differences between the structure, façade, services and other elements. Madaster explicitly aggregates products through building layers.[^1_6]

The weighting rule and software implementation should therefore be reported, rather than treating every “MCI” score as methodologically identical.[^1_6][^1_2]

## 5. Important qualifications for built-environment assessments

### Biological materials have additional rules

The 2019 methodology extends MCI to biological materials. It can recognise primary biological feedstock from sustained production, as well as qualifying biological end-of-use routes. This is not an automatic credit for anything labelled “renewable”: sourcing, contamination and biological accessibility matter. Timber, for example, should be evaluated using those provisions rather than simply classified as either virgin-linear or inherently circular.[^1_1]

### Recoverability is not the same as actual recovery

For a future building demolition, $C_R$ and $C_U$ are scenario assumptions. Theoretical recyclability does not establish that a material will actually be collected, recycled or reused. The methodology explicitly distinguishes design intent from real-world performance and supports sensitivity analyses for uncertain end-of-use scenarios.[^1_1]

For construction, the assessment should therefore make clear whether these fractions represent demonstrated recovery, current local practice, or a future design scenario. Design for disassembly supports recovery, but it is not itself a separate multiplier in the core MCI formula.[^1_1][^1_2]

### MCI does not replace LCA

MCI focuses on material flows and utility. It does not directly quantify embodied carbon, operational energy, toxicity, water use or material scarcity; the methodology calls for complementary indicators, including LCA-derived impacts. A higher MCI therefore does not, by itself, demonstrate a lower-carbon building.[^1_1]

### Simplified implementations can change the result

For example, eTool documents an implementation that assumes perfect recycling efficiency and uses a default $X=1$. Such a score does not capture recycling-process losses or the benefit of above-average longevity in the same way as the full calculation. Checking these assumptions is essential when comparing tools or published building scores.[^1_2]

For a reproducible assessment, report the material inventory and boundary, input-source fractions, end-of-use scenarios, recycling yields, service-life benchmarks, utility assumptions, and aggregation rule alongside the final MCI. Those choices explain what the score actually represents.[^1_4][^1_1][^1_2]

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://content.ellenmacarthurfoundation.org/m/77e62bc9924c20d0/original/Circularity-Indicators-Methodology.pdf

[^1_2]: https://support.etool.app/index.php/knowledgebase/circular-economy-material-circularity-indicator/

[^1_3]: https://nexus.openlca.org/ws/files/35569

[^1_4]: https://www.supplychainschool.co.uk/wp-content/uploads/2021/04/Circular-Economy-Indicators-and-Metrics-Tool-Guidance.pdf

[^1_5]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10951572/

[^1_6]: https://docs.madaster.com/nl/en/knowledge-base/calculations

[^1_7]: https://www.sciencedirect.com/science/article/pii/S0921344922003779

[^1_8]: https://www.tandfonline.com/doi/full/10.1080/14680629.2025.2483476

[^1_9]: https://air.iuav.it/handle/11578/332328

[^1_10]: https://www.thinkstep-anz.com/services/circular-economy/material-circularity-indicator-mci-calculator

[^1_11]: https://www.dataflex-int.com/en/our-story/news/sustainability-stories-material-circularity-indicator-mci

[^1_12]: https://www.hoskinscircular.com/blog/calculator-material-circularity-simple

[^1_13]: https://www.lenslab.polimi.it/material-circularity-indicator-mci/

[^1_14]: https://d-nb.info/1230543449/34

[^1_15]: https://www.sciencedirect.com/science/article/am/pii/S235255092200210X

[^1_16]: https://nexus.openlca.org/ws/files/25699

[^1_17]: https://nexus.openlca.org/ws/files/25687

[^1_18]: https://docs.rainbowstandard.io/methodologies/refurbishing-of-electronic-devices/circularity-assessment

[^1_19]: https://docs.rainbowstandard.io/methodologies/battery-second-life/circularity-assessment

[^1_20]: https://instituteofsustainabilitystudies.com/insights/lexicon/material-circularity-indicator-mci-a-key-metric-for-measuring-circularity/


---
