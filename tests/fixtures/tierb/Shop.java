// Fixture for Tier B symbols (Java).
package shop;

public class Shop {
    private int n;

    public void open() {}

    static class Inner {}
}

interface Cart {
    void add();
}

enum Status { OPEN, CLOSED }

record Item(String sku) {}
