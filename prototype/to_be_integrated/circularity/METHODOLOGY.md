# MCI calculation method

For mass $M$, recycled and reused input fractions $F_R$ and $F_U$, collection fractions $C_R$ and $C_U$, and recycling efficiencies $E_F$ and $E_C$:

$$V=M(1-F_R-F_U)$$

$$W_0=M(1-C_R-C_U)$$

$$W_F=M F_R\frac{1-E_F}{E_F},\qquad W_C=M C_R(1-E_C)$$

$$W=W_0+\frac{W_F+W_C}{2}$$

$$LFI=\frac{V+W}{2M+(W_F-W_C)/2}$$

Utility is:

$$X=\frac{L}{L_{av}}\frac{U}{U_{av}}$$

and the bounded score is:

$$MCI=\max\left(0,\min\left(1,1-LFI\frac{0.9}{X}\right)\right)$$

Material scores are mass-weighted to components, and pre-computed component scores are mass-weighted to layers and the building:

$$MCI_{building}=\frac{\sum_i M_i MCI_i}{\sum_i M_i}$$

The implementation validates fractions and prevents double counting between recycled/reused input and recycled/reused end-of-use routes. Recovery fractions describe a scenario; they should not be inferred from theoretical recyclability alone. Biological materials need the additional provisions of the 2019 MCI methodology and should be handled by a future explicit extension.
