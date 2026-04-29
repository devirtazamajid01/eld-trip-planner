/**
 * Leaflet's `divIcon` API requires an HTML string, not a React node,
 * so this helper returns SVG markup as a string instead of a JSX component.
 */
export const markerPinSvg = (color: string): string => `
  <svg
    width="20"
    height="26"
    viewBox="0 0 20 26"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path
      d="M10 0C4.477 0 0 4.477 0 10c0 7 10 16 10 16s10-9 10-16c0-5.523-4.477-10-10-10z"
      fill="${color}"
      stroke="white"
      stroke-width="1.5"
    />
    <circle cx="10" cy="10" r="4" fill="white" opacity="0.9" />
  </svg>
`;
