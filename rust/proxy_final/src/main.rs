mod tracepoint;
mod config;
mod pool;
mod proxy;

use clap::Parser;
use tokio::net::TcpListener;
use tokio::signal;
use std::error::Error;
use deadpool::managed::Pool;
use tracing::{info, error};
use crate::config::Config;
use crate::pool::TcpManager;
use crate::proxy::proxy_stream;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // 初始化日志
    tracing_subscriber::fmt::init();

    // 1. 读取配置 (通过命令行参数)
    let config = Config::parse();
    info!("Proxy configuration: {:?}", config);

    // 2. 初始化连接池
    let manager = TcpManager { addr: config.backend_addr };
    let pool_config = deadpool::managed::PoolConfig {
        max_size: 100,
        ..Default::default()
    };

    let pool = Pool::builder(manager)
        .config(pool_config)
        .build()?;

    info!("Backend TCP Pool initialized (Max: 100).");

    // 3. 启动监听器
    let listener = TcpListener::bind(config.proxy_addr).await?;
    info!("Proxy listening on {}", config.proxy_addr);

    // 4. 主事件循环
    loop {
        let sigint = signal::ctrl_c();
        tokio::select! {
            // 优雅关停
            _ = sigint => {
                info!("Shutting down gracefully...");
                break;
            },

            // 接受新连接
            result = listener.accept() => {
                match result {
                    Ok((stream, _)) => {
                        let proxy_pool = pool.clone();
                        let backend_addr = config.backend_addr;
                        tokio::spawn(async move {
                            proxy_stream(stream, proxy_pool, backend_addr).await;
                        });
                    }
                    Err(e) => {
                        error!("Error accepting connection: {}", e);
                    }
                }
            }
        }
    }

    info!("Proxy shut down completely.");
    Ok(())
}
