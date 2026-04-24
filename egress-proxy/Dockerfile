FROM golang:1.21-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/egress-proxy .

FROM scratch
COPY --from=build /out/egress-proxy /egress-proxy
USER 65532:65532
EXPOSE 3128
ENTRYPOINT ["/egress-proxy"]
