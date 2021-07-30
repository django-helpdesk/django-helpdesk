//TODO: 'High Performing' is not a type of property -- will need to add an array of 'high performing' types.

$('#id_e_is_affordable_housing').hide();
$('#id_e_property_type').change(function(){
    if($('#id_e_property_type').val() == "Multifamily Housing") {
        $('#id_e_is_affordable_housing').show();
    } else {
        $('#id_e_is_affordable_housing').hide();
    }
});

$('#id_e_type_affordable_housing').hide();
$('#id_e_property_type').change(function(){
    if($('#id_e_property_type').val() == "Multifamily Housing" && $('#id_e_is_affordable_housing').val()) {
        $('#id_e_type_affordable_housing').show();
    } else {
        $('#id_e_type_affordable_housing').hide();
    }
});

$('#id_e_acp_type').hide();
$('#id_e_property_type').change(function(){
    if($('#id_e_pathway').val() == "Alternative Compliance Pathway") {
        $('#id_e_acp_type').show();
    } else {
        $('#id_e_acp_type').hide();
    }
});

var alertMsg1 = 'This property type is not eligible for the Standard Target Pathway, please select another pathway.';
var alertMsg2 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this FAQ [link to be provided later].';
var alertMsg3 = 'This property type is not eligible for the Extended Deep Energy Retrofit ACP Option, please select another pathway.'
var alertMsg4 = 'You have selected the Extended Deep Energy Retrofit ACP Option, please note that DOEE will not approve this selection until the building owner has submitted a Proposed Extended Deep Energy Retrofit Milestone Plan. For more information please see this FAQ [link to be provided later].'
var alertMsg5 = 'You have selected the Custom ACP Option, please note that DOEE will not approve this selection until the building owner has submitted custom ACP Option proposal. For more information please see this FAQ [link to be provided later].'

jQuery.validator.addMethod('alert1', function (value, element, param) {
    return this.optional(element) || !($(param.path).val() == 'Standard Target Pathway' && !($(param.prop).val() == '' || $(param.prop).val() == 'High Performing'));
}, alertMsg1);

jQuery.validator.addMethod('alert2', function (value, element) {
    var ok = this.optional(element) || value != 'Prescriptive Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg2);

/*
This field appears
if "ACP Option" =  "Extended Deep Energy Retrofit"
AND ("Affordable Housing/Rent Controlled?" = FALSE
OR ("Primary Property Type - Portfolio Manager Calculated" != "College/University" OR "Hospital").
If this alert text appears the user should not be able to submit the form, until they select another pathway
*/
jQuery.validator.addMethod('alert3', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( !$(param.affordable).val() || ($(param.prop).val() != "College/University" || $(param.prop).val() != "Hospital")) );
}, alertMsg3);

/*
if "ACP Option" =  "Extended Deep Energy Retrofit"
AND ("Affordable Housing/Rent Controlled?" = TRUE
OR ("Primary Property Type - Portfolio Manager Calculated" = "College/University" OR "Hospital").
If this alert text appears the user should not be able to submit the form, until they select another pathway
*/
jQuery.validator.addMethod('alert4', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( $(param.affordable).val() || ($(param.prop).val() == "College/University" || $(param.prop).val() == "Hospital")) );
}, alertMsg4);

jQuery.validator.addMethod('alert5', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg5);

var form_validator = $('#ticket_submission_form').validate({
    ignore: '.error-okay',
    rules: {
        e_pathway: {
            alert2: true,
            alert5: true
        },
        e_property_type: {
            alert1: {
                param: {
                    path: '#id_e_pathway',
                    prop: '#id_e_property_type'
                }
            }
        },
        e_acp: {
            alert3: {
                param: {
                    affordable: '#id_e_is_affordable_housing',
                    prop: '#id_e_property_type'
                }
            },
            alert4: {
                param: {
                    affordable: '#id_e_is_affordable_housing',
                    prop: '#id_e_property_type'
                }
            },
        }
    },
});

$('#id_e_pathway').change(function(){
    if ($('#id_e_property_type').val() != '')
        form_validator.element('#id_e_property_type');
});

// alert3 and alert4
$('#id_e_property_type').change(function(){
    if ($('#id_e_acp').val() != '' && $('#id_e_is_affordable_housing').val() != null)
        form_validator.element('#id_e_acp');
});
$('#id_e_is_affordable_housing').change(function(){
    if ($('#id_e_acp').val() != '' && $('#id_e_property_type').val() != '')
        form_validator.element('#id_e_acp');
});

