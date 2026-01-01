use clap::Parser;
use std::net::SocketAddr;

#[derive(Parser, Debug, Clone)]
#[command(author, version, about, long_about = None)]
pub struct Config {
    /// Address to listen on
    #[arg(long, default_value = "0.0.0.0:8080")]
    pub proxy_addr: SocketAddr,

    /// Address of the backend server
    #[arg(long, default_value = "127.0.0.1:8000")]
    pub backend_addr: SocketAddr,
}
