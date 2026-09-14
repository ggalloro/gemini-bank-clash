# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /statements .

# Runtime stage
FROM alpine:3.20

RUN apk --no-cache add curl ca-certificates

WORKDIR /app

COPY --from=builder /statements /app/statements

EXPOSE 8083

ENTRYPOINT ["/app/statements"]
