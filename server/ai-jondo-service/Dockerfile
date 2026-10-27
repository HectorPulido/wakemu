FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish JondoAI.csproj -c Release -o /out --nologo

FROM mcr.microsoft.com/dotnet/runtime:8.0
WORKDIR /app
COPY --from=build /out .
ENV WAKFU_JONDO_BIND=0.0.0.0 WAKFU_JONDO_PORT=8091 DOTNET_EnableDiagnostics=0
USER $APP_UID
EXPOSE 8091
HEALTHCHECK --interval=5s --timeout=4s --start-period=5s --retries=3 CMD ["dotnet", "JondoAI.dll", "--health"]
ENTRYPOINT ["dotnet", "JondoAI.dll"]
