#include "bridge/device_connection_store.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <iostream>
#include <stdexcept>
using namespace nullxoid::device_connection_store;
static void check(bool value, const char *message) { if (!value) throw std::runtime_error(message); }
static QByteArray seal(const QByteArray &data) {
    DATA_BLOB input {DWORD(data.size()), reinterpret_cast<BYTE *>(const_cast<char *>(data.data()))}, out {};
    check(CryptProtectData(&input, L"AIBenchie disposable connection", nullptr, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &out), "protect");
    QByteArray result(reinterpret_cast<char *>(out.pbData), out.cbData); LocalFree(out.pbData); return result;
}
static void write(const QString &path, const QByteArray &data) {
    QFile file(path); check(file.open(QIODevice::WriteOnly), "open"); check(file.write(data)==data.size(), "write");
}
int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    QStandardPaths::setTestModeEnabled(true);
    QTemporaryDir temporary; check(temporary.isValid(), "temp");
    QCoreApplication::setApplicationName("AIBenchie-BridgeSetup-"+QString::number(QCoreApplication::applicationPid()));
    const auto key=QStringLiteral("disposable-device-key");
    const auto source=temporary.filePath("connection.dpapi");
    const QJsonObject value {{"version",1},{"deviceKey",key},{"plan",QJsonObject{{"server","https://example.test/"}}},
        {"token","synthetic-credential-never-used"},{"launcher",QJsonObject{{"config","synthetic"}}}};
    const auto sealed=seal(QJsonDocument(value).toJson(QJsonDocument::Compact));
    write(source,sealed);
    check(load(source,key)==value,"same-user roundtrip");
    check(load(source,"different-key").isEmpty(),"cross-device rejection");
    check(!sealed.contains("synthetic-credential-never-used"),"credential not plaintext");
    check(remember(source,key) && load(path(key),key)==value,"protected persistence");
    auto broken=sealed; broken[broken.size()/2]^=1; write(source,broken);
    check(load(source,key).isEmpty() && !remember(source,key),"tampered import rejection");
    check(load(path(key),key)==value,"failed import preserves stored connection");
    write(source,QByteArray(65537,'x')); check(load(source,key).isEmpty(),"oversized input rejection");
    auto invalid=value; invalid.remove("plan"); write(source,seal(QJsonDocument(invalid).toJson()));
    check(load(source,key).isEmpty(),"incomplete connection rejection");
    QFile::remove(path(key)); QDir().rmdir(QFileInfo(path(key)).absolutePath());
    std::cout<<"8 protected connection-store checks passed; synthetic only\n";
}
