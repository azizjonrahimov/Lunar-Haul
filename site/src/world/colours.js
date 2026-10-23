// Owner colours (Paul Tol bright), shared by the 3D scene, the plan view and the legend.
export const OWNER_COLOURS = { NASA: '#4477AA', CoA: '#EE6677', CoB: '#228833', CoC: '#CCBB44' };
export const EXTRA_COLOURS = ['#66CCEE', '#AA3377', '#BBBBBB'];
// On light surfaces (2D plans, legends) the bright Tol yellow, cyan and grey are below 3:1. The theme tokens carry the
// same hues, darker in the light theme and bright in the dark ones; 3D views keep the bright values (a dark sky).
const TOKEN = { '#CCBB44': '--tol-yellow', '#66CCEE': '--tol-cyan', '#BBBBBB': '--tol-grey' };
export const themedVar = hex => TOKEN[hex.toUpperCase()] ? `var(${TOKEN[hex.toUpperCase()]})` : hex;   // for HTML and SVG
export const themed = (hex, read) => (TOKEN[hex.toUpperCase()] && read(TOKEN[hex.toUpperCase()])) || hex;   // for a canvas (read = a CSS lookup)
