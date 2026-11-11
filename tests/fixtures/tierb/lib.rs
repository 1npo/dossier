// Fixture for Tier B symbols (Rust).
pub mod net {
    pub fn nested() {}
}

pub struct Config {
    pub name: String,
}

enum Mode {
    Fast,
    Slow,
}

pub trait Runner {
    fn run(&self);
}

type Alias = Vec<u8>;

impl Config {
    fn method(&self) {}
}

pub fn main() {}
