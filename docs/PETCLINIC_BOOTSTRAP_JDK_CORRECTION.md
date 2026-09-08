# Исправление установки JDK для Petclinic bootstrap

Вопрос следующего запуска: выполнится ли зафиксированный bootstrap при прямой установке того же официального JDK с проверкой SHA256? Ожидается прохождение установки и исполнение неизменных прикладных контролей.

Run 34198870157, head d548f01153d889f2a36c5d2c3bc32a6b4e9937fa остановился до установки study package, Maven/Docker/нагрузки: actions/setup-java@v5 отверг строку `17.0.20.1+1` как недопустимый SemVer. Это ограничение парсера action, а не отказ Petclinic и не результат проверки модели. Прикладных данных, сборки и прогнозов нет; исходный workflow сохранён.

Отдельный `petclinic-bootstrap-jdk-archive.yml` загружает официальный Linux x64 HotSpot JDK из [Temurin release jdk-17.0.20.1+1](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.20.1%2B1), проверяет фактический SHA256 `3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e` и добавляет его bin в PATH. Это тот же выбранный JDK, без нового выбора версии по результатам приложения. GitHub release asset metadata проверены до запуска. Распаковка использует Python tarfile data filter; источник/бинарные данные остаются remote.

Java-код Petclinic, четыре контракта, deadlines, SQL, agent, OCI digests, circuit-breaker/retry и все semantic/native gates остаются зафиксированными в исходном bootstrap. Полный протокол — [PETCLINIC_BOOTSTRAP_PROTOCOL.md](PETCLINIC_BOOTSTRAP_PROTOCOL.md). После выполнения сохраняются результаты и все 22 статуса. Старый setup failure остаётся в журнале; пересчитывать прежние научные результаты не требуется.
