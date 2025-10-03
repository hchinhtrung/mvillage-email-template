# M Village Email Templates

A comprehensive collection of email templates for M Village hotel booking platform, supporting multiple languages (English/Vietnamese) and various customer journey touchpoints.

## 📁 Template Categories

### 🏨 Booking Confirmations
- **1.bk-loyalty/** - Booking confirmations for loyalty program members
  - `bk-conf-EN.html` - English version
  - `bk-conf-VI.html` - Vietnamese version

- **2.bk-non-loyalty/** - Booking confirmations for non-loyalty customers
  - `bk-conf-non-loyalty-EN.html` - English version
  - `bk-conf-non-loyalty-VI.html` - Vietnamese version

- **3.bk-b2b/** - B2B booking confirmations
  - `bk-conf-b2b-EN.html` - English version
  - `bk-conf-b2b-VI.html` - Vietnamese version

### 🎯 Customer Journey
- **9.welcome/** - Welcome emails for new users
  - `email_welcome_en.html` - English welcome
  - `email_welcome_vi.html` - Vietnamese welcome

- **8.verify/** - Email verification
  - `verify.html` - Account verification email

- **10.remind-verify/** - Verification reminders
  - `remind-verify-EN.html` - English reminder
  - `remind-verify-VI.html` - Vietnamese reminder

- **22.pre-arrival/** - Pre-arrival notifications
  - `pre-arrival_en.html` - English pre-arrival
  - `pre-arrival_vi.html` - Vietnamese pre-arrival

### 📊 Surveys & Feedback
- **6.survey-loyalty/** - Post-stay surveys for loyalty members
  - `survey-loyalty-EN.html` - English survey
  - `survey-loyalty-VI.html` - Vietnamese survey

- **7.survey-non-loyalty/** - Post-stay surveys for non-loyalty customers
  - `survey-non-loyalty-EN.html` - English survey
  - `survey-non-loyalty-VI.html` - Vietnamese survey

- **17.start-review-loyalty/** - Review initiation for loyalty members
  - `start-review-loyalty-EN.html` - English version
  - `start-review-loyalty-VI.html` - Vietnamese version

- **18.end-review-loyalty/** - Review completion for loyalty members
  - `end-review-loyalty-EN.html` - English version
  - `end-review-loyalty-VI.html` - Vietnamese version

### 💰 Billing & Invoicing
- **5.einvoice/** - Electronic invoice templates
  - `einvoice-email.html` - Email invoice template
  - `einvoice-pms-template.html` - PMS invoice template
  - `einvoice-pms-updated.html` - Updated PMS template
  - `invoice-v2.html` - Version 2 invoice template

### 🏢 B2B & Corporate
- **4.b2b lead/** - B2B lead generation
  - `b2b.html` - B2B lead capture template

- **19.b2b-reminder/** - B2B follow-up reminders
  - `b2b-bao-gia.html` - Vietnamese pricing reminder
  - `b2b-reminder-v2-en.html` - English B2B reminder v2
  - `b2b-reminder-v2-vi.html` - Vietnamese B2B reminder v2

- **21.b2b-send-pass/** - B2B account credentials
  - `b2b-send-pass-en.html` - English credentials
  - `b2b-send-pass-vi.html` - Vietnamese credentials

### 🎖️ Loyalty Program
- **13.upgrade-tier/** - Tier upgrade notifications
  - `upgrade_tier_en.html` - English upgrade
  - `upgrade_tier_vi.html` - Vietnamese upgrade

- **14.downgrade-tier/** - Tier downgrade notifications
  - `downgrade_tier_en.html` - English downgrade
  - `downgrade_tier_vi.html` - Vietnamese downgrade

### 🏠 Landlord & Property Management
- **23.landlord/** - Landlord-specific templates
  - `landlord.html` - Main landlord template
  - `landlord-demo.html` - Demo version

### 🛠️ Tools & Utilities
- **12.tool/** - Utility templates and tools
  - `account_deletion_tool.html` - Account deletion template
  - `landlord-landing-page.html` - Landlord landing page
  - `original.html` - Original template
  - `survey-typeform-v1.html` - Typeform survey integration

- **15.python/** - Python automation scripts
  - `send-b2b-lead.py` - B2B lead automation script

### 📈 Process Documentation
- **16.flowchart-mermaidchart/** - Process flowcharts
  - `MV-pickup-profile.mmd` - Profile pickup flowchart
  - `MV-product-process.mmd` - Product process flowchart

### ⚠️ Issue Management
- **20.aware-issue/** - Issue awareness notifications
  - `aware-EN.html` - English issue notification
  - `aware-VI.html` - Vietnamese issue notification

## 🚀 Usage

### Template Variables
Most templates use Handlebars-style variables for dynamic content:
- `{{email}}` - Customer email
- `{{name}}` - Customer name
- `{{booking_id}}` - Booking reference
- `{{hotel_name}}` - Hotel name
- `{{check_in_date}}` - Check-in date
- `{{check_out_date}}` - Check-out date

### Python Automation
The B2B lead automation script (`15.python/send-b2b-lead.py`) can be used to send bulk B2B emails:
```bash
cd 15.python
python send-b2b-lead.py
```

### Email Client Compatibility
All templates are designed for maximum compatibility across email clients:
- Outlook (2007-2019)
- Gmail
- Apple Mail
- Yahoo Mail
- Mobile clients

## 🎨 Design Features

- **Responsive Design** - Mobile-optimized layouts
- **Cross-client Compatibility** - Works across all major email clients
- **Professional Typography** - Be Vietnam Pro font family
- **Brand Consistency** - M Village branding throughout
- **Accessibility** - Screen reader friendly

## 📝 Language Support

- **English (EN)** - Full English templates
- **Vietnamese (VI)** - Full Vietnamese templates
- **Bilingual Support** - Consistent messaging across languages

## 🔧 Technical Specifications

- **HTML5** - Modern HTML structure
- **CSS3** - Inline and embedded styles
- **MIME Type** - `text/html`
- **Character Encoding** - UTF-8
- **Viewport** - Responsive meta tags

## 📞 Support

For questions about template usage or customization, please contact the M Village development team.

---

*Last updated: $(date)*
