# Build server
FROM rust:1.77 as builder
COPY . .
WORKDIR /server
# This builds it and copies the executable to .
# https://doc.rust-lang.org/cargo/commands/cargo-install.html
RUN cargo build
RUN install /server/target/debug/biotools_linter_server /bin/server

WORKDIR /


#FROM debian:bookworm
#ENV DEBIAN_FRONTEND=noninteractive
#RUN apt-get update && apt-get install pkg-config libssl3 libssl-dev python3-pip python3 -y && rm -rf /var/lib/apt/lists/*
#COPY --from=builder /app/server/target/debug/biotools_linter_server /bin/server

#COPY . .
RUN install entrypoint.sh /bin
EXPOSE 8080

#CMD ["/bin/server"]
ENTRYPOINT [ "entrypoint.sh" ]
