export interface RoutePoint {
  id: string;
  day: number;
  order: number;
  name: string;
  type?: string;
  city?: string;
  time?: string;
  meta?: string;
  lnglat?: [number, number];
}
