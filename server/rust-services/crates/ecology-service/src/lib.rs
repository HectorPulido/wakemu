//! External ecology planning and durable delivery. World retains live authority.

pub mod catalog;
pub mod config;
pub mod http;
pub mod identity;
pub mod planners;
pub mod protocol;
pub mod repository;
pub mod worker;
pub mod world_client;

pub struct Context {
    pub db: deadpool_postgres::Pool,
    pub catalog: catalog::Catalog,
}
