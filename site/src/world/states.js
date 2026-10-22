// Rover states of the scene packages (B-31) and how /world/ draws them; shared by the 3D scene and the 2D plan
// (kept free of three.js so the tier-0 plan loads light).
// state -> [ring colour (Tol bright / the instrument accents), plain words]
export const STATE_STYLE = {
  idle: ['#d7dde6', 'idle'], driving: ['#6fcde9', 'driving'], loading: ['#228833', 'loading or unloading'], team_lift: ['#66CCEE', 'carrying with a team'],
  parked_night: ['#8a8f99', 'parked for the night'], standdown: ['#f0a54a', 'holding outside a landing keep-out'],
  waiting_for_earth: ['#AA3377', 'waiting for Earth (no link)'], failed: ['#EE6677', 'recovering from a fault'],
};
