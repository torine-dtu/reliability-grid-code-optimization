# This file contains the mathematical formulation of the full optimization problem from the paper :)
$$
    \begin{aligned}
        \min_{\boldsymbol{\xi}}\quad\overbrace{\sum_{t,i} c_{t,i}(1-\varepsilon_t)b_{t,i}}^\text{reserve provision cost} +\overbrace{\sum_{t,\omega}\pi_{t,\omega}\left( \rho^{\rm{viol}}s_{t,\omega}^{\rm viol} + \rho^{\rm{sys}} s_{t,\omega}^{\rm sys}\right)}^\text{reserve shortfall cost} \\
        \text{s.t.}\quad s_{t,i,\omega} \geq 0, 
        \forall t,i,\omega, \\
        s_{t,i,\omega} \geq b_{t,i} - r_{t,i,\omega},
        \forall t,i,\omega,\\
         s_{t,\omega}^{\rm viol} = \sum_i s_{t,i,\omega}, 
        \forall t,\omega,\\
        s^{\rm sys}_{t,\omega}\geq 0,
        \forall t,\omega,\\
        s^{\rm sys}_{t,\omega}\geq D_t-d_t+
        s_{t,\omega}^{\rm viol},\forall 
        t,\omega,\\
        d_t - s_{t,\omega}^{\rm viol} + My_{t,\omega} 
        \geq D_t, \forall t,\omega,  \\
        |\Omega|-\sum_\omega y_{t,\omega} \geq 
        |\Omega|(1-\varepsilon^{\rm sys}),
        \forall t, \\
        y_{t,\omega}\in\{0,1\},\forall 
        t,\omega, \\
        0.8\leq (1-\varepsilon_t) \leq 1,
        \forall t,\\
        \hat{b}_{t,i}\leq z_{t,i},\forall t,i, \\
        -\hat{b}_{t,i} \leq 0,\forall t,i,\\
        -1+\bar{\mu}_{t,i}-\underline{\mu}_{t,i}=0, 
        \forall t,i, \\
        -\bar{\mu}_{t,i}z_{t,i}\geq-\hat{b}_{t,i}, 
        \forall t,i, \\
        b_{t,i} \leq \hat{b}_{t,i},  \forall t,i, \\
        -b_{t,i}\leq 0,  \forall t,i, \\
        d_{t} - \sum_i b_{t,i} = 0,  \forall t, \\
        \alpha_{t,i} + (1-\varepsilon_t)\beta_{t,i}-\underline{\nu}_{t,i}+
        \bar{\nu}_{t,i}-\lambda_t=0, \forall t,i, 
        \\
        \sum_i-\bar{\nu}_{t,i}\hat{b}_{t,i}+
        \lambda_t d_t \nonumber\\ \geq\sum_i \left(\alpha_{t,i} + (1-\varepsilon_t)\beta_{t,i}\right)
        b_{t,i}, \forall t, \\
        \bar{\mu}_{t,i},\underline{\mu}_{t,i},
        \bar{\nu}_{t,i},\underline{\nu}_{t,i}\geq 0, 
        \quad\lambda_t\text{ free}, \forall t,i, 
        \text{where}
        F^{-1}\left(\frac{\varepsilon_t}{0.2}\right)
        =:z_{t,i}. 
    \end{aligned}
$$
