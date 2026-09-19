#include "app/credential_file_sign_in.h"
#include <QCoreApplication>
#include <QEventLoop>
#include <QTemporaryDir>
#include <iostream>
#include <stdexcept>

using namespace nullxoid;
static int passed = 0;
static void check(bool ok, const char *label) {
    if (!ok) throw std::runtime_error(label);
    ++passed;
}
static void write(const QString &path, const QByteArray &bytes) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size()) throw std::runtime_error("fixture write");
}
static QJsonObject request(const QString &name, const QByteArray &payload) {
    QLocalSocket client;
    QEventLoop loop;
    QTimer timeout;
    timeout.setSingleShot(true);
    QByteArray response;
    QObject::connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);
    QObject::connect(&client, &QLocalSocket::connected, &loop, [&] { client.write(payload); });
    QObject::connect(&client, &QLocalSocket::readyRead, &loop, [&] {
        response += client.readAll();
        if (response.contains('\n')) loop.quit();
    });
    client.connectToServer(name);
    timeout.start(3000);
    loop.exec();
    if (response.isEmpty()) throw std::runtime_error("local response timeout");
    return QJsonDocument::fromJson(response).object();
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        QTemporaryDir dir;
        const auto path = dir.filePath("credentials.txt");
        const QByteArray valid = "\xef\xbb\xbf" "Test fixture\r\nUsername: artistic\r\nPassword: dummy: with spaces \r\n";
        FileCredentials credentials;
        write(path, valid);
        check(readFileCredentials(path, credentials) && credentials.username == "artistic" &&
              credentials.password == "dummy: with spaces ", "BOM, CRLF, colon and significant spaces");
        write(path, "Username: first\nUsername: second\nPassword: dummy\n");
        check(!readFileCredentials(path, credentials) && credentials.password.isEmpty(), "ambiguous labels");
        write(path, "Username: artistic\n");
        check(!readFileCredentials(path, credentials), "missing password");
        write(path, QByteArray(65537, 'a'));
        check(!readFileCredentials(path, credentials), "oversized file");
        write(path, QByteArray("Username: artistic\nPassword: ")+char(0xff));
        check(!readFileCredentials(path, credentials), "invalid UTF8");
        check(!readFileCredentials("relative.txt", credentials), "relative path");
        check(credentialDestinationMatches("https://api.example.test", "https://api.example.test/"), "same origin");
        check(!credentialDestinationMatches("https://api.example.test", "https://other.example.test"), "different host");
        check(!credentialDestinationMatches("http://api.example.test", "http://api.example.test"), "cleartext refused");
        check(!credentialDestinationMatches("https://api.example.test", "https://api.example.test/?next=evil"), "query refused");

        write(path, valid);
        CredentialFileSignIn::State state{false, {}, false};
        int logins = 0;
        bool fail = false;
        CredentialFileSignIn server("https://api.example.test", [&] { return state; },
            [&](const QString &username, const QString &password) {
                check(username == "artistic" && password == "dummy: with spaces ", "existing login callback data");
                ++logins;
                state.busy = true;
                QTimer::singleShot(10, &app, [&] { state = {!fail, fail ? QString{} : QString("artistic"), false}; });
            });
        const auto name = QString("AIBenchie.SignIn.%1").arg(app.applicationPid());
        check(server.listen(name), "same-user local listener");
        QCoreApplication::processEvents();
        check(logins == 0, "no automatic sign-in without a request");
        const QJsonObject input{{"action", "sign-in-from-file"}, {"credentialsFile", path},
                                {"expectedBackend", "https://api.example.test"}};
        const auto bytes = QJsonDocument(input).toJson(QJsonDocument::Compact) + '\n';
        auto result = request(name, bytes);
        check(result.value("ok").toBool() && result.value("username") == "artistic" && logins == 1, "confirmed sign-in");
        check(!QJsonDocument(result).toJson().contains("dummy"), "no secret in result");
        result = request(name, bytes);
        check(result.value("ok").toBool() && logins == 1, "repeat preserves signed-in session");
        state.username = "other-account";
        check(!request(name, bytes).value("ok").toBool() && logins == 1, "no silent account switch");
        state = {false, {}, false};
        auto wrong = input;
        wrong["expectedBackend"] = "https://wrong.example.test";
        check(!request(name, QJsonDocument(wrong).toJson(QJsonDocument::Compact)+'\n').value("ok").toBool() && logins == 1,
              "destination mismatch cannot invoke login");
        fail = true;
        check(!request(name, bytes).value("ok").toBool() && logins == 2, "failed auth not reported as success");
        fail = false;
        state.busy = true;
        QTimer::singleShot(150, &app, [&] { state.busy = false; });
        check(request(name, bytes).value("ok").toBool() && logins == 3, "bootstrap continuation");
        check(!request(name, QByteArray(8193, 'x')+'\n').value("ok").toBool() && logins == 3, "bounded request");
        std::cout << passed << " credential-helper checks passed; synthetic, not phone acceptance\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
