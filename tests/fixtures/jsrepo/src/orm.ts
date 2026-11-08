import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity() // @model-orm
export class Product {
  @PrimaryGeneratedColumn() id!: number;
  @Column() name!: string;
  @Column() price!: number;
}
