use async_trait::async_trait;
use deadpool::managed::{Manager, RecycleError, RecycleResult};
use std::net::SocketAddr;
use tokio::net::TcpStream;
use tokio::io::Interest;
use tokio::time::{timeout, Duration};

pub struct TcpManager {
    pub addr: SocketAddr,
}

#[async_trait]
impl Manager for TcpManager {
    type Type = TcpStream;
    type Error = RecycleError<()>;

    async fn create(&self) -> Result<Self::Type, Self::Error> {
        TcpStream::connect(self.addr)
            .await
            .map_err(|e| RecycleError::Message(e.to_string()))
    }

    async fn recycle(&self, conn: &mut Self::Type, _: &deadpool::managed::Metrics) -> RecycleResult<Self::Error> {
        match timeout(Duration::from_millis(1), conn.ready(Interest::READABLE)).await {
            Ok(Ok(ready)) if ready.is_readable() => {
                let mut buf = [0u8; 1];
                match conn.try_read(&mut buf) {
                    Ok(0) => Err(RecycleError::Message("EOF".into())),
                    Ok(_) => Err(RecycleError::Message("unexpected data".into())),
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => Ok(()),
                    Err(e) => Err(RecycleError::Message(e.to_string())),
                }
            }
            _ => Err(RecycleError::Message("health check timeout".into())),
        }
    }
}

pub type TcpPool = deadpool::managed::Pool<TcpManager>;
