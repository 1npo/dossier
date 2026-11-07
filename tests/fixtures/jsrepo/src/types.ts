export enum Status {
  Open,
  Paid,
}

export interface Order { // @model-order
  id: number;
  total: number;
  status: Status;
  note?: string;
}

export type Item = { // @model-item
  sku: string;
  qty: number;
};

export interface ButtonProps {
  label: string;
}

interface Local {
  x: number;
}

export const origin: Local = { x: 0 };
