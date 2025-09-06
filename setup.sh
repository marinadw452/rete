#!/bin/bash

# ==========================================
# سكريبت إعداد وتشغيل نظام طقطق
# ==========================================

set -e  # التوقف عند أي خطأ

# ألوان للمخرجات
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# دالة طباعة ملونة
print_step() {
    echo -e "${BLUE}==>${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✅${NC} ${1}"
}

print_error() {
    echo -e "${RED}❌${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} ${1}"
}

print_info() {
    echo -e "${CYAN}ℹ️${NC} ${1}"
}

# بداية السكريبت
clear
echo -e "${PURPLE}
╔══════════════════════════════════════╗
║           🚖 نظام طقطق                ║
║        إعداد وتشغيل النظام           ║
╚══════════════════════════════════════╝${NC}
"

# التحقق من المتطلبات
print_step "التحقق من المتطلبات..."

# التحقق من Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker غير مثبت. يرجى تثبيت Docker أولاً"
    exit 1
fi

# التحقق من Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose غير مثبت. يرجى تثبيت Docker Compose أولاً"
    exit 1
fi

print_success "جميع المتطلبات متوفرة"

# التحقق من الملفات المطلوبة
print_step "التحقق من الملفات المطلوبة..."

required_files=(
    "main.py"
    "config.py" 
    "docker-compose.yml"
    "Dockerfile"
    "requirements.txt"
    "init.sql"
    "neighborhoods.json"
)

missing_files=()
for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        missing_files+=("$file")
    fi
done

if [[ ${#missing_files[@]} -gt 0 ]]; then
    print_error "الملفات التالية مفقودة:"
    printf '  - %s\n' "${missing_files[@]}"
    exit 1
fi

print_success "جميع الملفات المطلوبة موجودة"

# التحقق من إعدادات البوت
print_step "التحقق من إعدادات البوت..."

if grep -q "YOUR_BOT_TOKEN_HERE" config.py; then
    print_warning "تحتاج لتعديل BOT_TOKEN في ملف config.py"
    echo -e "${CYAN}احصل على التوكن من: https://t.me/BotFather${NC}"
    read -p "هل تريد المتابعة؟ (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# التحقق من ملف الأحياء
print_step "التحقق من ملف الأحياء..."
if [[ ! -s "neighborhoods.json" ]]; then
    print_warning "ملف neighborhoods.json فارغ أو غير موجود"
    echo "سيتم إنشاء ملف تجريبي..."
    
    cat > neighborhoods.json << 'EOF'
{
  "الرياض": [
    "الملز", "العليا", "الخرج", "الشفا", "النسيم", "الروضة",
    "السليمانية", "الياسمين", "النرجس", "الوادي", "الربوة"
  ],
  "جدة": [
    "البلد", "الحمراء", "الروضة", "الزهراء", "الكورنيش", "النزهة",
    "الصفا", "الشاطئ", "السلامة", "البوادي", "الثعالبة"
  ]
}
EOF
    print_success "تم إنشاء ملف neighborhoods.json"
fi

# إنشاء المجلدات المطلوبة
print_step "إنشاء المجلدات..."
mkdir -p logs backups

# بناء وتشغيل النظام
print_step "بناء صور Docker..."
docker-compose build

print_step "تشغيل النظام..."
docker-compose up -d

# انتظار بدء الخدمات
print_step "انتظار بدء الخدمات..."
sleep 10

# التحقق من حالة الخدمات
print_step "التحقق من حالة الخدمات..."

if docker-compose ps | grep -q "Up"; then
    print_success "تم تشغيل النظام بنجاح!"
    echo
    print_info "معلومات مفيدة:"
    echo -e "  🔗 لوحة إدارة قاعدة البيانات: ${CYAN}http://localhost:8080${NC}"
    echo -e "  📊 لعرض حالة الخدمات: ${YELLOW}make status${NC}"
    echo -e "  📜 لعرض السجلات: ${YELLOW}make logs${NC}"
    echo
    print_info "بيانات الاتصال بقاعدة البيانات:"
    echo -e "  📡 الخادم: ${CYAN}postgres${NC}"
    echo -e "  👤 المستخدم: ${CYAN}postgres${NC}"
    echo -e "  🔐 كلمة المرور: ${CYAN}taktak123${NC}"
    echo -e "  🗄️ قاعدة البيانات: ${CYAN}taktak_db${NC}"
    echo
else
    print_error "فشل في تشغيل النظام"
    echo "تحقق من السجلات:"
    echo "  docker-compose logs"
    exit 1
fi

# اختبار الاتصال بقاعدة البيانات
print_step "اختبار الاتصال بقاعدة البيانات..."
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    print_success "قاعدة البيانات متصلة ومتاحة"
else
    print_warning "قاعدة البيانات غير متاحة حالياً"
fi

# إحصائيات النظام
print_step "عرض إحصائيات النظام..."
echo
echo -e "${PURPLE}📊 حالة النظام:${NC}"
docker-compose ps

echo -e "
${GREEN}🎉 تم إعداد نظام طقطق بنجاح!${NC}

${YELLOW}الخطوات التالية:${NC}
1. تأكد من تعديل BOT_TOKEN في config.py
2. اختبر البوت على تليجرام
3. راقب السجلات: make logs

${CYAN}أوامر مفيدة:${NC}
  make status     - حالة الخدمات
  make logs       - عرض السجلات
  make restart    - إعادة تشغيل
  make clean      - تنظيف
  make backup     - نسخة احتياطية

${PURPLE}نتمنى لك تجربة رائعة مع نظام طقطق! 🚖${NC}
"
