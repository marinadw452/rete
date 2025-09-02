# ==========================================
# Makefile لنظام طقطق
# ==========================================

# متغيرات
DOCKER_COMPOSE = docker-compose
PROJECT_NAME = taktak
DB_CONTAINER = taktak_postgres
BOT_CONTAINER = taktak_bot

# ألوان للمخرجات
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help build up down restart logs clean install test backup restore

# عرض قائمة الأوامر
help:
	@echo "$(GREEN)📋 أوامر نظام طقطق$(NC)"
	@echo ""
	@echo "$(YELLOW)⚙️  الإعداد والتشغيل:$(NC)"
	@echo "  make install    - تثبيت المتطلبات"
	@echo "  make build      - بناء الصور"
	@echo "  make up         - تشغيل النظام"
	@echo "  make down       - إيقاف النظام"
	@echo "  make restart    - إعادة تشغيل النظام"
	@echo ""
	@echo "$(YELLOW)📊 المراقبة والصيانة:$(NC)"
	@echo "  make logs       - عرض السجلات"
	@echo "  make logs-bot   - عرض سجلات البوت"
	@echo "  make logs-db    - عرض سجلات قاعدة البيانات"
	@echo "  make status     - حالة الخدمات"
	@echo "  make ps         - عرض الحاويات"
	@echo ""
	@echo "$(YELLOW)🗄️  قاعدة البيانات:$(NC)"
	@echo "  make db-shell   - الدخول لقاعدة البيانات"
	@echo "  make backup     - نسخ احتياطي"
	@echo "  make restore    - استعادة النسخة الاحتياطية"
	@echo "  make db-reset   - إعادة تعيين قاعدة البيانات"
	@echo ""
	@echo "$(YELLOW)🧹 التنظيف:$(NC)"
	@echo "  make clean      - تنظيف الحاويات المتوقفة"
	@echo "  make clean-all  - تنظيف شامل"

# تثبيت المتطلبات
install:
	@echo "$(GREEN)📦 تثبيت المتطلبات...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✅ تم تثبيت المتطلبات$(NC)"

# بناء الصور
build:
	@echo "$(GREEN)🔨 بناء صور دوكر...$(NC)"
	$(DOCKER_COMPOSE) build
	@echo "$(GREEN)✅ تم بناء الصور$(NC)"

# تشغيل النظام
up:
	@echo "$(GREEN)🚀 تشغيل نظام طقطق...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ تم تشغيل النظام$(NC)"
	@echo "$(YELLOW)📊 لعرض لوحة الإدارة: http://localhost:8080$(NC)"
	@echo "$(YELLOW)📋 لعرض الحالة: make status$(NC)"

# إيقاف النظام
down:
	@echo "$(YELLOW)⏹️  إيقاف النظام...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ تم إيقاف النظام$(NC)"

# إعادة تشغيل النظام
restart:
	@echo "$(YELLOW)🔄 إعادة تشغيل النظام...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)✅ تم إعادة تشغيل النظام$(NC)"

# عرض السجلات
logs:
	@echo "$(GREEN)📜 سجلات النظام:$(NC)"
	$(DOCKER_COMPOSE) logs -f

# عرض سجلات البوت فقط
logs-bot:
	@echo "$(GREEN)🤖 سجلات البوت:$(NC)"
	$(DOCKER_COMPOSE) logs -f $(BOT_CONTAINER)

# عرض سجلات قاعدة البيانات
logs-db:
	@echo "$(GREEN)🗄️  سجلات قاعدة البيانات:$(NC)"
	$(DOCKER_COMPOSE) logs -f $(DB_CONTAINER)

# حالة الخدمات
status:
	@echo "$(GREEN)📊 حالة خدمات طقطق:$(NC)"
	$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "$(GREEN)🔗 الروابط المفيدة:$(NC)"
	@echo "$(YELLOW)لوحة إدارة قاعدة البيانات: http://localhost:8080$(NC)"

# عرض الحاويات
ps:
	@echo "$(GREEN)📦 الحاويات النشطة:$(NC)"
	docker ps --filter "name=$(PROJECT_NAME)"

# الدخول لقاعدة البيانات
db-shell:
	@echo "$(GREEN)🗄️  الاتصال بقاعدة البيانات...$(NC)"
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d taktak_db

# نسخة احتياطية من قاعدة البيانات
backup:
	@echo "$(GREEN)💾 إنشاء نسخة احتياطية...$(NC)"
	@mkdir -p backups
	$(DOCKER_COMPOSE) exec postgres pg_dump -U postgres taktak_db > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ تم إنشاء النسخة الاحتياطية في مجلد backups$(NC)"

# استعادة النسخة الاحتياطية
restore:
	@echo "$(YELLOW)⚠️  استعادة النسخة الاحتياطية...$(NC)"
	@read -p "اسم ملف النسخة الاحتياطية: " backup_file; \
	if [ -f "backups/$$backup_file" ]; then \
		$(DOCKER_COMPOSE) exec -T postgres psql -U postgres taktak_db < backups/$$backup_file; \
		echo "$(GREEN)✅ تم استعادة النسخة الاحتياطية$(NC)"; \
	else \
		echo "$(RED)❌ الملف غير موجود$(NC)"; \
	fi

# إعادة تعيين قاعدة البيانات
db-reset:
	@echo "$(RED)⚠️  إعادة تعيين قاعدة البيانات (سيتم حذف جميع البيانات!)$(NC)"
	@read -p "هل أنت متأكد؟ اكتب 'yes' للتأكيد: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE) down; \
		docker volume rm $(PROJECT_NAME)_postgres_data 2>/dev/null || true; \
		$(DOCKER_COMPOSE) up -d postgres; \
		sleep 5; \
		$(DOCKER_COMPOSE) up -d; \
		echo "$(GREEN)✅ تم إعادة تعيين قاعدة البيانات$(NC)"; \
	else \
		echo "$(YELLOW)❌ تم إلغاء العملية$(NC)"; \
	fi

# تنظيف الحاويات المتوقفة
clean:
	@echo "$(GREEN)🧹 تنظيف الحاويات المتوقفة...$(NC)"
	docker container prune -f
	docker image prune -f
	@echo "$(GREEN)✅ تم التنظيف$(NC)"

# تنظيف شامل
clean-all:
	@echo "$(RED)🧹 تنظيف شامل (حذف جميع البيانات!)$(NC)"
	@read -p "هل أنت متأكد؟ اكتب 'yes' للتأكيد: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE) down -v; \
		docker system prune -af; \
		echo "$(GREEN)✅ تم التنظيف الشامل$(NC)"; \
	else \
		echo "$(YELLOW)❌ تم إلغاء العملية$(NC)"; \
	fi

# اختبار الاتصال
test:
	@echo "$(GREEN)🧪 اختبار الاتصال...$(NC)"
	@if $(DOCKER_COMPOSE) exec postgres pg_isready -U postgres > /dev/null 2>&1; then \
		echo "$(GREEN)✅ قاعدة البيانات متصلة$(NC)"; \
	else \
		echo "$(RED)❌ قاعدة البيانات غير متصلة$(NC)"; \
	fi

# مراقبة الموارد
monitor:
	@echo "$(GREEN)📊 مراقبة استخدام الموارد:$(NC)"
	docker stats $(shell docker ps --filter "name=$(PROJECT_NAME)" --format "{{.Names}}")

# تحديث الصور
update:
	@echo "$(GREEN)🔄 تحديث صور دوكر...$(NC)"
	$(DOCKER_COMPOSE) pull
	$(DOCKER_COMPOSE) build --pull
	@echo "$(GREEN)✅ تم التحديث$(NC)"

# بدء سريع (الكل في أمر واحد)
quick-start: build up
	@echo "$(GREEN)🎉 تم تشغيل نظام طقطق بنجاح!$(NC)"

# إعادة التشغيل السريع
quick-restart: down up
	@echo "$(GREEN)🎉 تم إعادة تشغيل النظام بنجاح!$(NC)"
